# -*- coding: utf-8 -*-
# TODO: 大文字小文字の区別
import json
import os
import settings
import logging
import re
from lambda_base import LambdaBase
from jsonschema import validate, ValidationError
from botocore.exceptions import ClientError
from user_util import UserUtil


class MeAliasCreate(LambdaBase):
    def get_schema(self):
        return {
            'type': 'object',
            'properties': {
                'alias_user_id': settings.parameters['user_id']
            }
        }

    def validate_params(self):
        params = json.loads(self.event.get('body'))
        if params['alias_user_id'] in settings.ng_user_name:
            raise ValidationError('This username is not allowed')
        validate(params, self.get_schema())

    def exec_main_proc(self):
        params = self.event
        body = json.loads(params.get('body'))
        users_table = self.dynamodb.Table(os.environ['USERS_TABLE_NAME'])
        sns_users_table = self.dynamodb.Table(os.environ['SNS_USERS_TABLE_NAME'])
        user_id = params['requestContext']['authorizer']['claims']['cognito:username']
        exist_check_user = users_table.get_item(Key={'user_id': body['alias_user_id']}).get('Item')

        sns_user = sns_users_table.get_item(Key={'user_id': user_id}).get('Item')

        if (sns_user is not None) and ('alias_user_id' in sns_user):
            raise ValidationError('The alias id of this user has been added.')

        elif exist_check_user is None:
            # SNSのidで作成したcognitoのユーザーを除去
            UserUtil.delete_sns_id_cognito_user(self.cognito, user_id)

            # alias_user_idでのユーザーの作成のし直し
            try:
                email = sns_user['email']
                hash_data = sns_user['password']
                byte_hash_data = hash_data.encode()
                backed_password = UserUtil.decrypt_password(byte_hash_data)

                backed_temp_password = self.__generate_temp_pass(sns_user)
                provider = self.__generate_provider(sns_user)

                response = UserUtil.create_sns_user(
                    cognito=self.cognito,
                    user_id=body['alias_user_id'],
                    email=email,
                    backed_temp_password=backed_temp_password,
                    backed_password=backed_password,
                    provider=provider
                )

                UserUtil.force_non_verified_phone(
                    cognito=self.cognito,
                    user_id=body['alias_user_id']
                )

                UserUtil.wallet_initialization(self.cognito, os.environ['COGNITO_USER_POOL_ID'], body['alias_user_id'])

                # SnsUsersテーブルにaliasを追加
                UserUtil.add_alias_to_sns_user(body['alias_user_id'], sns_users_table, user_id)

                # Usersテーブルにユーザーを作る
                UserUtil.update_user_profile(
                    dynamodb=self.dynamodb,
                    user_id=body['alias_user_id'],
                    user_display_name=sns_user['user_display_name'],
                    icon_image=sns_user['icon_image_url']
                )

                has_alias_user_id = UserUtil.has_alias_user_id(self.dynamodb, user_id)

                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'access_token': response['AuthenticationResult']['AccessToken'],
                        'last_auth_user': body['alias_user_id'],
                        'id_token': response['AuthenticationResult']['IdToken'],
                        'refresh_token': response['AuthenticationResult']['RefreshToken'],
                        'status': 'login',
                        'has_alias_user_id': has_alias_user_id
                    })
                }

            except ClientError as e:
                logging.fatal(e)
                return {
                    'statusCode': 500,
                    'body': json.dumps({'message': 'Internal server error'})
                }

        else:
            raise ValidationError('This id is already in use.')

    @staticmethod
    def __generate_temp_pass(sns_user):
        if re.match('^LINE_U', sns_user['user_id']):
            return os.environ['LINE_LOGIN_COMMON_TEMP_PASSWORD']
        elif re.match('^Twitter', sns_user['user_id']):
            return 'twitterpass'  # os.environ['TWITTER_LOGIN_COMMON_TEMP_PASSWORD']

    @staticmethod
    def __generate_provider(sns_user):
        if re.match('^LINE_U', sns_user['user_id']):
            return os.environ['LINE_LOGIN_MARK']
        elif re.match('^Twitter', sns_user['user_id']):
            return 'twitter'
