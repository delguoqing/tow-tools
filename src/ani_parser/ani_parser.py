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
	for bone_name, ani_offset in sorted(bone_name_2_offset.items(), key=operator.itemgetter(1)):
		if last_off is not None:
			print "\tsize = 0x%x" % (ani_offset - last_off)	
		print "@offset:0x%x \t%s" % (ani_offset, bone_name)
		last_off = ani_offset
		
		print _G(ani_offset, "<IIIHH")
		
if __name__ == '__main__':
	input = sys.argv[1]
	
	
	fp = open(sys.argv[1], "rb")
	data = fp.read()
	fp.close()
	
	parse(data)
	