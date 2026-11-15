"""OpenAI-compatible chat client using raw HTTP (httpx) to bypass SDK filtering for Gemini 3.5."""
from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from .config import CONFIG


@dataclass
class LLMReply:
    content: str = ""
    reasoning: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, Any] = field(default_factory=dict)
    elapsed: float = 0.0


class LLM:
    def __init__(self):
        c = CONFIG["llm"]
        self.model = c["model"]
        self.base_url = c["base_url"].rstrip("/")
        self.api_key = c["api_key"]
        self.timeout = c.get("timeout_s", 240)
        self._sem = threading.Semaphore(int(c.get("max_streams", 4)))
        self.default_thinking = bool(c.get("thinking", True))
        self.max_tokens = int(c.get("max_tokens", 4000))
        self._qwen_endpoint = self._detect_qwen_endpoint()
        
        # ใช้ httpx ตรงๆ ไม่ผ่าน OpenAI SDK
        self.client = httpx.Client(timeout=self.timeout)

    def _detect_qwen_endpoint(self) -> bool:
        url = (self.base_url or "").lower()
        model = (self.model or "").lower()
        if any(k in url for k in ("vllm", "sglang", "localhost", "127.0.0.1", "0.0.0.0")):
            return True
        if "qwen" in model:
            return True
        return False

    def chat(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None, thinking: bool | None = None, max_tokens: int | None = None, temperature: float = 0.6, tool_choice: str | None = None, _allow_retry: bool = True) -> LLMReply:
        thinking = self.default_thinking if thinking is None else thinking
        
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature,
        }
        
        if self._qwen_endpoint:
            payload["chat_template_kwargs"] = {"enable_thinking": thinking}
            
        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        t0 = time.time()
        
        # 💡 Retry สำหรับ 429 (Rate Limit) และ 503 (Server Unavailable)
        max_retries = 10
        for attempt in range(max_retries):
            with self._sem:
                resp = self.client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                
            if resp.status_code == 200:
                break
                
            # 💡 Retry ทั้ง 429 (Rate Limit) และ 503 (Server Unavailable)
            if resp.status_code in (429, 503):
                try:
                    # ดึงเวลาที่ Gemini บอกให้รอ (ทั้งจาก Header และจากข้อความ)
                    wait_time = resp.headers.get("Retry-After")
                    if wait_time:
                        wait_time = float(wait_time) + 2.0
                    else:
                        match = re.search(r"retry in ([\d\.]+)s", resp.text)
                        wait_time = float(match.group(1)) + 2.0 if match else 30.0
                    wait_time = min(wait_time, 120.0) 
                    print(f"\n[Server Error {resp.status_code}] รอ {wait_time:.1f} วินาที... (ครั้งที่ {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                except Exception:
                    pass
            
            # ถ้าเป็น Error อื่น หรือ Retry ครบแล้วยังไม่ผ่าน
            raise Exception(f"HTTP {resp.status_code}: {resp.text}")

        data = resp.json()
        if not data.get("choices"):
            raise Exception(f"Bad response: {data}")
            
        msg = data["choices"][0]["message"]
        reply = LLMReply(elapsed=time.time() - t0)
        reply.content = msg.get("content") or ""
        reply.raw_message = msg
        reply.reasoning = msg.get("reasoning_content") or msg.get("reasoning") or ""
        
        if msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                try:
                    args = json.loads(tc["function"]["arguments"] or "{}")
                except json.JSONDecodeError:
                    args = {"_raw": tc["function"]["arguments"]}
                
                sig = None
                if "extra_content" in tc and isinstance(tc["extra_content"], dict):
                    sig = tc["extra_content"].get("google", {}).get("thought_signature")
                
                reply.tool_calls.append({
                    "id": tc["id"], 
                    "name": tc["function"]["name"], 
                    "arguments": args,
                    "_thought_signature": sig
                })
                
        if data.get("usage"):
            reply.usage = data["usage"]
            
        if _allow_retry and thinking and not reply.content.strip() and not reply.tool_calls:
            return self.chat(messages, tools, thinking=False, max_tokens=max_tokens, temperature=temperature, tool_choice=tool_choice, _allow_retry=False)
        return reply

    def assistant_message(self, reply: LLMReply) -> dict[str, Any]:
        m: dict[str, Any] = {"role": "assistant", "content": reply.content or ""}
        if reply.tool_calls:
            m["tool_calls"] = []
            for tc in reply.tool_calls:
                tool_call_dict = {
                    "id": tc["id"], 
                    "type": "function", 
                    "function": {
                        "name": tc["name"], 
                        "arguments": json.dumps(tc["arguments"])
                    }
                }
                
                if not self._qwen_endpoint:
                    sig = tc.get("_thought_signature") or "skip_thought_signature_validator"
                    tool_call_dict["extra_content"] = {"google": {"thought_signature": sig}}
                    
                m["tool_calls"].append(tool_call_dict)
        return m