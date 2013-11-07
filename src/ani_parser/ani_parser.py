import sys
import operator
import struct

MAGIC_CODE = "ANI\x00"

def parse(data):
	
	# short cut for parsing value from 'data'
	def _G(offset, fmt):
		fmt_size = struct.calcsize(fmt)
		return struct.unpack(fmt, data[offset: offset + fmt_size])
		
	if not data.startswith(MAGIC_CODE):
		print "unknown format!"
		return

	ani_count, = _G(0x4, "<I")
	
	# guess
	bone_count, = _G(0xc, "<I")
	frame_count, frame_rate = _G(0x10, "<II")
	print "bone_count = %d" % bone_count
	print "fps = %d, key frame count = %d" % (frame_rate, frame_count)
	
	print "frame count int = %d" % _G(0x18, "I")
	
	assert frame_rate == 30 and frame_count == 160, "hey!!!!!!!"
	
	bone_name_2_offset = {}
	for bone_index in xrange(bone_count):
		bone_offset = 0x1c + bone_index * (0x20 + 0x4)
		# guess begin
		ani_offset, = _G(bone_offset + 0x20, "<I")
		bone_name, = _G(bone_offset, "<32s")
		bone_name = bone_name.rstrip("\x00")
		
		bone_name_2_offset[bone_name] = ani_offset
		
	last_off = None
	key_count = 0
	for bone_name, ani_offset in sorted(bone_name_2_offset.items(), key=operator.itemgetter(1)):
		if last_off is not None:
			print "\tsize = 0x%x" % (ani_offset - last_off)
			
			remain_float_count = (ani_offset - last_off - 0x8 - 0x4 * key_count) / 0x4
			print "remaining floats(%d): @ offset = 0x%x" % (remain_float_count, ani_offset - remain_float_count * 0x4)
			remain_floats = _G(ani_offset - remain_float_count * 0x4, "<" + "f" * remain_float_count)
				
					
		print "@offset:0x%x \t%s" % (ani_offset, bone_name)
		last_off = ani_offset
		
		# guess
		key_count, unknown = _G(ani_offset, "<II")
		print "key_frame_count = %d" % (key_count, )
		
		if True or unknown != 0x7:
			print "==============>unknown = 0x%x" % unknown
		#assert unknown == 7, str(unknown)
		print "key frames @: ", ",".join(map(repr, _G(ani_offset + 0x8, "<" + "I" * key_count)))
		
		unknown2, = _G(ani_offset + 0x8 + 0x4 * key_count, "<I")
		unknown2_half = (unknown2 >> 16)
		assert unknown2_half == unknown, ("what?0x%x" % unknown2_half)
		#assert unknown2 == 0x70000, str(unknown2)
		if True or unknown2 != 0x70000:
			print "==============>unknown2 = 0x%x" % unknown2
		
		key_frame_offset = ani_offset + 0x8 + 0x4 * key_count
		for key_index in xrange(key_count):
			flag1, flag2 = _G(key_frame_offset, "<HH")
			key_frame_offset += 4
			print "0x%x, 0x%x" % (flag1, flag2)
			if flag2 == 0x7:
				float_count = 10
			elif flag2 == 0x2:
				float_count = 4
			elif flag2 == 0x3:
				float_count = 7
			elif flag2 == 0x1:
				float_count = 3
			else:
				assert False, "unknown flag !!! %d @ 0x%x" % (flag2, key_frame_offset)
			print _G(key_frame_offset, "<" + "f" * float_count)
			key_frame_offset += 0x4 * float_count
		
if __name__ == '__main__':
	input = sys.argv[1]
	
	744
	11
	
	
	fp = open(sys.argv[1], "rb")
	data = fp.read()
	fp.close()
	
	parse(data)
	