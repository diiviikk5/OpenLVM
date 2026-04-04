"""Python FFI bindings for the OpenLVM Zig core runtime."""

from __future__ import annotations

import ctypes
import struct
import sys
from pathlib import Path
from typing import ClassVar, List, Optional

# Constants based on core/src/chaos.zig
CHAOS_MODE_NETWORK_DELAY = 0
CHAOS_MODE_NETWORK_DROP = 1
CHAOS_MODE_API_ERROR = 2
CHAOS_MODE_HALLUCINATION = 3
CHAOS_MODE_MEMORY_PRESSURE = 4
CHAOS_MODE_CPU_THROTTLE = 5
CHAOS_MODE_CLOCK_SKEW = 6
CHAOS_MODE_TOOL_FAILURE = 7

# Event types based on core/src/replay.zig
EVENT_LLM_REQUEST = 0
EVENT_LLM_RESPONSE = 1
EVENT_TOOL_CALL = 2
EVENT_TOOL_RESULT = 3


class OpenLVMError(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"{message} (Error code: {code})")


class OpenLVMRuntime:
    """Thin wrapper around the shared Zig runtime."""

    _shared_lib: ClassVar[ctypes.CDLL | None] = None
    _instance_count: ClassVar[int] = 0

    def __init__(self, lib_path: Optional[str] = None):
        if OpenLVMRuntime._shared_lib is None:
            resolved_path = lib_path or self._default_library_path()
            if not Path(resolved_path).exists():
                raise FileNotFoundError(
                    f"OpenLVM shared library not found at: {resolved_path}. Did you build the Zig core?"
                )
            lib = ctypes.CDLL(str(resolved_path))
            self._configure_signatures(lib)
            res = lib.openlvm_init()
            if res < 0 and res != -2:
                raise OpenLVMError(res, "Failed to initialize OpenLVM runtime")
            OpenLVMRuntime._shared_lib = lib

        self._lib = OpenLVMRuntime._shared_lib
        OpenLVMRuntime._instance_count += 1
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        OpenLVMRuntime._instance_count = max(0, OpenLVMRuntime._instance_count - 1)
        if OpenLVMRuntime._instance_count == 0 and OpenLVMRuntime._shared_lib is not None:
            OpenLVMRuntime._shared_lib.openlvm_shutdown()
            OpenLVMRuntime._shared_lib = None

    def __enter__(self) -> "OpenLVMRuntime":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self):
        if hasattr(self, "_closed") and not self._closed:
            self.close()

    @staticmethod
    def _default_library_path() -> Path:
        if sys.platform == "win32":
            lib_name = "openlvm.dll"
        elif sys.platform == "darwin":
            lib_name = "libopenlvm.dylib"
        else:
            lib_name = "libopenlvm.so"
        root_dir = Path(__file__).resolve().parents[2]
        return root_dir / "core" / "zig-out" / "lib" / lib_name

    @staticmethod
    def _configure_signatures(lib: ctypes.CDLL) -> None:
        lib.openlvm_init.restype = ctypes.c_int32
        lib.openlvm_shutdown.restype = ctypes.c_int32
        lib.openlvm_register_agent.argtypes = [ctypes.c_uint64]
        lib.openlvm_register_agent.restype = ctypes.c_int64
        lib.openlvm_terminate_agent.argtypes = [ctypes.c_uint64]
        lib.openlvm_terminate_agent.restype = ctypes.c_int32
        lib.openlvm_active_agent_count.restype = ctypes.c_int64
        lib.openlvm_fork_agent.argtypes = [ctypes.c_uint64]
        lib.openlvm_fork_agent.restype = ctypes.c_int64
        lib.openlvm_fork_many.argtypes = [ctypes.c_uint64, ctypes.c_uint32, ctypes.POINTER(ctypes.c_int64)]
        lib.openlvm_fork_many.restype = ctypes.c_int32
        lib.openlvm_snapshot_create.argtypes = [ctypes.c_uint64]
        lib.openlvm_snapshot_create.restype = ctypes.c_int64
        lib.openlvm_replay_start.argtypes = [ctypes.c_uint64]
        lib.openlvm_replay_start.restype = ctypes.c_int64
        lib.openlvm_replay_stop.argtypes = [ctypes.c_uint64]
        lib.openlvm_replay_stop.restype = ctypes.c_int32
        lib.openlvm_chaos_add.argtypes = [ctypes.c_uint8, ctypes.c_uint64, ctypes.c_double, ctypes.c_uint64]
        lib.openlvm_chaos_add.restype = ctypes.c_int32
        lib.openlvm_chaos_get_delay.argtypes = [ctypes.c_uint64]
        lib.openlvm_chaos_get_delay.restype = ctypes.c_uint64
        lib.openlvm_version_major.restype = ctypes.c_uint32
        lib.openlvm_version_minor.restype = ctypes.c_uint32
        lib.openlvm_version_patch.restype = ctypes.c_uint32

    def register_agent(self, caps_bitmask: int) -> int:
        res = self._lib.openlvm_register_agent(ctypes.c_uint64(caps_bitmask))
        if res < 0:
            raise OpenLVMError(res, "Failed to register agent")
        return int(res)

    def terminate_agent(self, agent_id: int) -> None:
        res = self._lib.openlvm_terminate_agent(ctypes.c_uint64(agent_id))
        if res < 0:
            raise OpenLVMError(res, f"Failed to terminate agent {agent_id}")

    def get_active_agent_count(self) -> int:
        return int(self._lib.openlvm_active_agent_count())

    def fork_agent(self, agent_id: int) -> int:
        res = self._lib.openlvm_fork_agent(ctypes.c_uint64(agent_id))
        if res < 0:
            raise OpenLVMError(res, "Fork operation failed")
        return int(res)

    def fork_many(self, agent_id: int, count: int) -> List[int]:
        out_array = (ctypes.c_int64 * count)()
        res = self._lib.openlvm_fork_many(ctypes.c_uint64(agent_id), ctypes.c_uint32(count), out_array)
        if res < 0:
            raise OpenLVMError(res, "Fork_many operation failed")
        return [int(value) for value in out_array[:res]]

    def snapshot_create(self, agent_id: int) -> int:
        res = self._lib.openlvm_snapshot_create(ctypes.c_uint64(agent_id))
        if res < 0:
            raise OpenLVMError(res, "Failed to create snapshot")
        return int(res)

    def replay_start(self, agent_id: int) -> int:
        res = self._lib.openlvm_replay_start(ctypes.c_uint64(agent_id))
        if res < 0:
            raise OpenLVMError(res, "Failed to start recording")
        return int(res)

    def replay_stop(self, recording_id: int) -> None:
        res = self._lib.openlvm_replay_stop(ctypes.c_uint64(recording_id))
        if res < 0:
            raise OpenLVMError(res, f"Failed to stop recording {recording_id}")

    def chaos_add_network_delay(self, agent_id: int, probability: float, delay_ms: int) -> None:
        self._chaos_add(CHAOS_MODE_NETWORK_DELAY, agent_id, probability, delay_ms)

    def chaos_add_hallucination(self, agent_id: int, probability: float, corruption_rate: float) -> None:
        bits = struct.unpack("<Q", struct.pack("<d", corruption_rate))[0]
        self._chaos_add(CHAOS_MODE_HALLUCINATION, agent_id, probability, bits)

    def _chaos_add(self, mode: int, agent_id: int, probability: float, param: int) -> None:
        res = self._lib.openlvm_chaos_add(
            ctypes.c_uint8(mode),
            ctypes.c_uint64(agent_id),
            ctypes.c_double(probability),
            ctypes.c_uint64(param),
        )
        if res < 0:
            raise OpenLVMError(res, f"Failed to add chaos config for mode {mode}")

    def chaos_get_network_delay(self, agent_id: int) -> int:
        return int(self._lib.openlvm_chaos_get_delay(ctypes.c_uint64(agent_id)))

    def version(self) -> str:
        major = self._lib.openlvm_version_major()
        minor = self._lib.openlvm_version_minor()
        patch = self._lib.openlvm_version_patch()
        return f"{major}.{minor}.{patch}"
