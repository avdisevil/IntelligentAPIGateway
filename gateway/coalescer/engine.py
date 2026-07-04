"""
gateway/coalescer/engine.py

Public re-export of the coalescing engine.
The implementation lives in coalescer/manager.py (RequestCoalescer).
This module exists for import path consistency with the original design.
"""
from gateway.coalescer.manager import RequestCoalescer

__all__ = ["RequestCoalescer"]
