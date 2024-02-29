import os
from http import HTTPStatus
from typing import Dict, Iterator, List, Optional

import dashscope

from qwen_agent.llm.base import ModelServiceError, register_llm
from qwen_agent.llm.function_calling import BaseFnCallModel

from .schema import CONTENT, ROLE, ContentItem, Message


@register_llm('qwenvl_dashscope')
class QwenVLChatAtDS(BaseFnCallModel):

    def __init__(self, cfg: Optional[Dict] = None):
        super().__init__(cfg)
        self.model = self.model or 'qwen-vl-max'

        cfg = cfg or {}
        api_key = cfg.get('api_key', '')
        if not api_key:
            api_key = os.getenv('DASHSCOPE_API_KEY', 'EMPTY')
        api_key = api_key.strip()
        dashscope.api_key = api_key

    def _chat_stream(
        self,
        messages: List[Message],
        delta_stream: bool = False,
    ) -> Iterator[List[Message]]:
        if delta_stream:
            raise NotImplementedError

        messages = [msg.model_dump() for msg in messages]
        response = dashscope.MultiModalConversation.call(
            model=self.model,
            messages=messages,
            result_format='message',
            stream=True,
            **self.generate_cfg)

        for trunk in response:
            if trunk.status_code == HTTPStatus.OK:
                yield _extract_vl_response(trunk)
            else:
                err = '\nError code: %s. Error message: %s' % (
                    trunk.code,
                    trunk.message,
                )
                raise ModelServiceError(err)

    def _chat_no_stream(
        self,
        messages: List[Message],
    ) -> List[Message]:
        messages = [msg.model_dump() for msg in messages]
        response = dashscope.MultiModalConversation.call(
            model=self.model,
            messages=messages,
            result_format='message',
            stream=False,
            **self.generate_cfg)
        if response.status_code == HTTPStatus.OK:
            return _extract_vl_response(response=response)
        else:
            err = '\nError code: %s, error message: %s' % (
                response.code,
                response.message,
            )
            raise ModelServiceError(err)


def _extract_vl_response(response) -> List[Message]:
    output = response.output.choices[0].message
    text_content = []
    for item in output[CONTENT]:
        for k, v in item.items():
            if k in ('text', 'box'):
                text_content.append(ContentItem(text=v))
    return [Message(role=output[ROLE], content=text_content)]
