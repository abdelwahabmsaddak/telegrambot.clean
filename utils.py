# -*- coding: utf-8 -*-

def safe_text(text: str) -> str:
    if not text:
        return ""
    return (
        text
        .replace("\u200e", "")
        .replace("\u200f", "")
        .encode("utf-8", "ignore")
        .decode("utf-8")
    )
