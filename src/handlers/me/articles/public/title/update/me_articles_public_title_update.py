# -*- coding: utf-8 -*-
import os
import settings
from lambda_base import LambdaBase
from jsonschema import validate, FormatChecker
from text_sanitizer import TextSanitizer
from db_util import DBUtil
from user_util import UserUtil


class MeArticlesPublicTitleUpdate(LambdaBase):
    def get_schema(self):
        return {
            'type': 'object',
            'properties': {
                'article_id': settings.parameters['article_id'],
                'title': settings.parameters['title']
            },
            'required': ['article_id', 'title']
        }

    def validate_params(self):
        UserUtil.verified_phone_and_email(self.event)
        validate(self.params, self.get_schema(), format_checker=FormatChecker())

        DBUtil.validate_article_existence(
            self.dynamodb,
            self.params['article_id'],
            user_id=self.event['requestContext']['authorizer']['claims']['cognito:username'],
            status='public',
            version=2
        )

    def exec_main_proc(self):
        article_content_edit_table = self.dynamodb.Table(os.environ['ARTICLE_CONTENT_EDIT_TABLE_NAME'])

        expression_attribute_values = {
            ':user_id': self.event['requestContext']['authorizer']['claims']['cognito:username'],
            ':title': TextSanitizer.sanitize_text(self.params.get('title'))
        }
        DBUtil.items_values_empty_to_none(expression_attribute_values)

        article_content_edit_table.update_item(
            Key={
                'article_id': self.params['article_id'],
            },
            UpdateExpression="set user_id=:user_id, title=:title",
            ExpressionAttributeValues=expression_attribute_values
        )

        return {
            'statusCode': 200
        }
