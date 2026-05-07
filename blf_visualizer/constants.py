"""
BLF binary format constants.
Add new object types here when extending parser support.
"""

FILE_SIGNATURE_PREFIX = b"LOGG"
OBJECT_SIGNATURE      = b"LOBJ"

# Object types
OBJ_CAN_MESSAGE       = 1
OBJ_CAN_ERROR         = 2
OBJ_LOG_CONTAINER     = 10
OBJ_CAN_ERROR_EXT     = 73
OBJ_CAN_MESSAGE2      = 86
OBJ_CAN_FD_MESSAGE    = 105
OBJ_CAN_FD_MESSAGE_64 = 108

COMPRESSION_ZLIB = 2
