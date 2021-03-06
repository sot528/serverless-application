# -*- coding: utf-8 -*-
import json
import settings
from es_util import ESUtil
from lambda_base import LambdaBase
from jsonschema import validate
from decimal_encoder import DecimalEncoder
from parameter_util import ParameterUtil


class SearchArticles(LambdaBase):
    def get_schema(self):
        return {
            'type': 'object',
            'properties': {
                'limit': settings.parameters['limit'],
                'page': settings.parameters['page'],
                'query': settings.parameters['query'],
                'tag': settings.parameters['tag']
            },
            'anyOf': [
                {'required': ['query']},
                {'required': ['tag']},
            ]
        }

    def validate_params(self):
        ParameterUtil.cast_parameter_to_int(self.params, self.get_schema())
        validate(self.params, self.get_schema())

    def exec_main_proc(self):
        query = self.params.get('query')
        tag = self.params.get('tag')
        limit = int(self.params.get('limit')) if self.params.get('limit') is not None else settings.article_recent_default_limit
        page = int(self.params.get('page')) if self.params.get('page') is not None else 1
        response = ESUtil.search_article(self.elasticsearch, limit, page, word=query, tag=tag)
        result = []
        for a in response["hits"]["hits"]:
            del(a["_source"]["body"])
            result.append(a["_source"])
        return {
            'statusCode': 200,
            'body': json.dumps(result, cls=DecimalEncoder)
        }
