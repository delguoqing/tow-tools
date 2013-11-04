import sys
import struct

NOD_HEADER = "NOD\x00"

BLOCK_TYPE_ROOT = 1
BLOCK_TYPE_CHILD = 3

def parse(data):
	
	# short cut for parsing value from 'data'
	def _G(offset, fmt):
		fmt_size = struct.calcsize(fmt)
		return struct.unpack(fmt, data[offset: offset + fmt_size])
	
	# check header
	if not data.startswith(NOD_HEADER):
		print "unknown format!\n"
		return
		
	bone_name_len = 0x20
	bone_count, = _G(0x10, "<I")
	
	# guess
	# 0x1 --> describe a root bone
	# 0x3 --> describe a child-parent pair
	
	block_size = 0x4 + bone_name_len * 2
	
	for block_index in xrange(bone_count):
		block_offset = 0x14 + block_index * block_size
		type, name1, name2 = _G(block_offset, "<I32s32s")
		name1 = name1.rstrip("\x00")
		name2 = name2.rstrip("\x00")
		
		if type == BLOCK_TYPE_ROOT:
			assert name2 == "#0", "root block format error!"
			parent = name2
			child = name1
		elif type == BLOCK_TYPE_CHILD:
			parent = name2
			child = name1
		else:
			assert False, "unknown block type"
		
		print "%s -> %s" % (parent, child)
		
if __name__ == '__main__':
	fp = open(sys.argv[1], "rb")
	data = fp.read()
	fp.close()
	
	parse(data)