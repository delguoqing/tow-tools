import sys
import operator
import struct
import numpy

MAGIC_CODE = "ANI\x00"

BIT_USE_MATRIX = 0x100	# use matrix directly
BIT_HAS_TRANSLATE = 0x1
BIT_HAS_ROTATE = 0x2	# in the form of quaternion.
						# This can be verfied easily by calculate the norm.
						# w*w + x*x + y*y + z*z.It should be 1.0
BIT_HAS_SCALE = 0x4


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
		
	print
	
	key_count = 0
	for bone_name, ani_offset in sorted(bone_name_2_offset.items(), key=operator.itemgetter(1)):					
		print "%s  @offset:0x%x" % (bone_name, ani_offset)
		
		# guess
		key_count, flag_all = _G(ani_offset, "<II")
		print "key_frame_count = %d, flag_all = 0x%x" % (key_count, flag_all)
		
		key_frame_offsets = _G(ani_offset + 0x8, "<" + "I" * key_count)

		key_frame_offset_next = ani_offset + 0x8 + key_count * 0x4
		
		for key_index in xrange(key_count):
			key_frame_offset = key_frame_offsets[key_index] + ani_offset
			
			assert key_frame_offset_next == key_frame_offset, "not matched!"
			
			flag1, flag2 = _G(key_frame_offset, "<HH")
			key_frame_offset += 4
			print "key@frame %4d, flags=0x%x" % (flag1, flag2)
			
			use_matrix = (flag2 & BIT_USE_MATRIX)
			if use_matrix:
				jii = _G(key_frame_offset, "<" + "f" * 9)
				arr = numpy.array(jii)
				arr.shape = (3, 3)
				print "socket:"
				print numpy.mat(arr)
				
				sys.stderr.write("socket @ %s\n" % bone_name)
				
				key_frame_offset += 0x9 * 0x4
			
			float_count = 0
				
			if flag2 & BIT_HAS_TRANSLATE:
				float_count += 3
			if flag2 & BIT_HAS_ROTATE:
				float_count += 4
			if flag2 & BIT_HAS_SCALE:
				float_count += 3
				
			floats = _G(key_frame_offset, "<" + "f" * float_count)
			#print floats
			
			if flag2 & BIT_HAS_TRANSLATE:
				print "\ttranslate: (%f, %f, %f)" % (floats[:3])
				floats = floats[3:]
				
			if flag2 & BIT_HAS_ROTATE:
				assert abs(calc_sum_of_squares(floats[:4]) - 1.0) < 1e-6, "quaternion norm should be 1.0"
				print "\trotate: (%f, %f, %f, %f)" % floats[:4]
				floats = floats[4:]
				
			if flag2 & BIT_HAS_SCALE:
				print "\tscale: (%f, %f, %f)" % floats[:3]
				floats = floats[3:]
				
			key_frame_offset_next = key_frame_offset + 0x4 * float_count
		
		print
		
def calc_sum_of_squares(values):
	result = 0
	for value in values:
		result += value * value
	return result
	
if __name__ == '__main__':
	input = sys.argv[1]
	
	fp = open(sys.argv[1], "rb")
	data = fp.read()
	fp.close()
	
	parse(data)
	