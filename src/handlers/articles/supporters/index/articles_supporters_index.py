import json
import math
import os
from itertools import groupby

from boto3.dynamodb.conditions import Key
from jsonschema import ValidationError, validate

import settings
from db_util import DBUtil
from decimal_encoder import DecimalEncoder
from lambda_base import LambdaBase


class ArticlesSupportersIndex(LambdaBase):
    def get_schema(self):
        return {
            'type': 'object',
            'properties': {
                'article_id': settings.parameters['article_id']
            },
            'required': ['article_id']
        }

    def validate_params(self):
        # single
        params = self.event.get('pathParameters')

        if params is None:
            raise ValidationError('pathParameters is required')

        validate(params, self.get_schema())
        # relation
        DBUtil.validate_article_existence(
            self.dynamodb,
            params['article_id'],
            status='public'
        )

    def exec_main_proc(self):
        tip_table = self.dynamodb.Table(os.environ['SUCCEEDED_TIP_TABLE_NAME'])

        query_params = {
            'IndexName': 'article_id-sort_key-index',
            'KeyConditionExpression': Key('article_id').eq(self.params['article_id'])
        }

        tips = tip_table.query(**query_params)['Items']

        users_tip_values = {}

        for k, g in groupby(sorted(tips, key=lambda item: item['user_id']), key=lambda item: item['user_id']):
            tip_value = sum([tip['tip_value'] for tip in g])
            users_tip_values[k] = {'tip_value': tip_value}

        users = self.__bulk_get_users(list(users_tip_values.keys()))

        users_with_tip = []
        for user in users:
            user_id = user['user_id']
            user.update(users_tip_values[user_id])
            user_data = {
                'user_id': user['user_id'],
                'user_display_name': user['user_display_name'],
                'sum_tip_value': users_tip_values[user_id]['tip_value']
            }
            icon_image_url = user.get('icon_image_url')
            if icon_image_url is not None:
                user_data['icon_image_url'] = icon_image_url
            users_with_tip.append(user_data)

        sorted_users_with_tip = sorted(users_with_tip, key=lambda item: item['sum_tip_value'], reverse=True)

        return {
            'statusCode': 200,
            'body': json.dumps({'Items': sorted_users_with_tip}, cls=DecimalEncoder)
        }

    # user_idの配列を受け取ってDynamoDBにbulk_getをし、userオブジェクトの配列を返却するメソッド
    def __bulk_get_users(self, user_ids):
        # DynamoDBのbatchGetは100件までしか対応してないため、100件ごとにsplitする
        split_user_ids = [
            user_ids[index * settings.DYNAMO_BATCH_GET_MAX:(index + 1) * settings.DYNAMO_BATCH_GET_MAX]
            for index
            in range(math.ceil(len(user_ids) / settings.DYNAMO_BATCH_GET_MAX))
        ]

        users = []

        user_table_name = os.environ['USERS_TABLE_NAME']

        for split_user_id in split_user_ids:
            response = self.dynamodb.batch_get_item(
                RequestItems={
                    user_table_name: {
                        'Keys': [{'user_id': user_id} for user_id in split_user_id]
                    }
                }
            )
            for user in response['Responses'][user_table_name]:
                users.append(user)

        return users
