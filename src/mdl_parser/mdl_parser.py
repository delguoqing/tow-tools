import os
import sys
import struct
import numpy
import re
import glob
import operator
import functools
import pspgu_consts

verbers = True

def log(str):
	if verbers:
		print str
		
def parse(data, filename):
	def _G(offset, fmt):
		fmt_size = struct.calcsize(fmt)
		return struct.unpack(fmt, data[offset: offset + fmt_size])
	def _P(name, value_fmt, locals):
		value_fmt = value_fmt.replace("%", "%%(%s)" % name)
		fmt = "%s = %s" % (name, value_fmt)
		log(fmt % locals)
		
	# check header
	MAGIC_CODE = "MDL\x00"
	magic_code = data[0: len(MAGIC_CODE)]
	if magic_code != MAGIC_CODE:
		raise Exception("unknown file format!")

	# figured out stuff a.t.m
	matrix_count, = _G(0x1c, "<I")
	bone_count, = _G(0x24, "<I")
	unknown, = _G(0x20, "<I")	# texture_count??
	_P("matrix_count", "%d", locals())
	_P("bone_count", "%d", locals())
	
	
	# matrix
	matrix_offset_base = 0x4c + (unknown - 0x4) * 0x4
	vertex_count, = _G(matrix_offset_base-0x4, "<I")

	log("unknown values in between")
	unks = _G(0x28, "<"+"I"*((matrix_offset_base-0x2c)/0x4))
	log("%r" % (unks,))
	
	_P("vertex_count", "%d", locals())
	log("matrix offset base = 0x%x" % matrix_offset_base)
	for i in xrange(matrix_count):
		matrix_offset = matrix_offset_base + i * 0x3c
		array = numpy.array(_G(matrix_offset, "<ffffffffffff") + (0, 0, 0, 1))
		array.shape = (4, 4)
		matrix = numpy.array(array.copy())
		log("%r" % matrix)
		unk_offset = matrix_offset + 12*0x4
		unks2 = _G(unk_offset, "<iHHBBBB")
		log("unknown values following: %r\n" % (unks2,))

	#	if unks[i+3] != unks2[3]:
	#		print "test failed"
	#		return
	#
	#print "test ok"
	
	unk_offset = matrix_offset_base + matrix_count * (12+3) * 0x4
	unks3 = _G(unk_offset, "<II")
	log("unknown values before bones %r" % (unks3,))
	# bone info blocks
	bone_offset_base = unk_offset + 0x8
	
	for i in xrange(bone_count):
		bone_offset = bone_offset_base + i * 0xa0
		bone_name_end = data.index("\x00", bone_offset)
		bone_name = data[bone_offset: bone_name_end]
		
		log("bone: %s" % bone_name)
		fvals = _G(bone_offset + 0x20, "<" + "ffff" * 8)
		#print fvals

		array = numpy.array(fvals[:16])
		array.shape = (4, 4)
		matrix1 = numpy.mat(array.copy())
		
		array = numpy.array(fvals[16:])
		array.shape = (4, 4)
		matrix2 = numpy.mat(array.copy())
		
		assert fvals[:16] == fvals[16:]
		#log("%r" % matrix1)

	# vertex blocks
	vertex_block_offset = bone_offset_base + 0xa0 * bone_count
	vertex_data = []
	for _ in xrange(10):
		if vertex_block_offset >= len(data):
			break
		print "VERTEX BLOCK %d, offset=0x%x" % (_, vertex_block_offset)
		# vertex block header
		header = _G(vertex_block_offset, "<IIIIIiiff")
		
		vertex_format_bits = header[2]
		vertex_count = header[3]
		
		print "raw header", header
		print "vertex count %d" % vertex_count
		print "vertex format bits = %d" % vertex_format_bits
		format_strings, converters = str_vertex_format(vertex_format_bits)
		total_size = 0
		for count, size, converter in converters:
			total_size += count * size
		print "total_size 0x%x" % total_size
		print "\n".join(format_strings)
		
		# vertices
		vertices = []
		vertices_offset_base = vertex_block_offset + 9 * 0x4
		for i in xrange(vertex_count):
			vertex_offset = vertices_offset_base + i * total_size
			print "===>vertex %d: offset = 0x%x" % (i, vertex_offset)
			
			_offset = vertex_offset
			values = []
			for count, size, converter in converters:
				_tmp = []
				for j in range(count):
					_tmp.append(converter(data[_offset: _offset + size]))
					_offset += size
				values.append(_tmp)
				
			w, vt, c, n, vp = values
			
			if w:
				print "w ", " ".join(map(str,w))
				w = w[0]
			else:
				w = None
			if vt:
				print "vt ", " ".join(map(str,vt))
				u, v = vt[:2]
			else:
				u, v = None, None
			if c:
				print "c 0x%08x" % c[0]
				c = c[0]
			else:
				c = None
			if n:
				print "n ", " ".join(map(str,n))
				nx, ny, nz = n[:3]
			else:
				nx, ny, nz = None, None, None
			if vp:
				print "v ", " ".join(map(str,vp))
				x, y, z = vp[:3]
			else:
				x, y, z = None, None, None
			vertices.append((w, u, v, c, nx, ny, nz, x, y, z))
			
		vertex_data.append(vertices)
		vertex_block_offset += 9 * 0x4 + vertex_count * total_size
		if vertex_block_offset % 0x4 != 0:
			vertex_block_offset += 4 - vertex_block_offset % 0x4
	
	dump_to_obj_file(filename, vertex_data)

def make_converter(fmt, fp_shift=1):
	def convert(data):
		a, = struct.unpack(fmt, data)
		a /= fp_shift
		return a
	return convert
		
HCONV = make_converter("<H")
ICONV = make_converter("<I")
F8CONV = make_converter("<b", 16.0)
F16CONV = make_converter("<h", 256.0)
F32CONV = make_converter("<f")

def str_vertex_format(bits):
	mask = pspgu_consts.GU_WEIGHTS_BITS
	weight_n = 0
	for i in xrange(1, 9, 1):
		if (mask & bits) == pspgu_consts.GU_WEIGHTS(i):
			weight_n = i
			bits -= pspgu_consts.GU_WEIGHTS(i)
			break
	print "weight_n = %d" % weight_n
	
	CHECK_ITEMS = (
		("weight bits: %d", 0, pspgu_consts.GU_WEIGHT_BITS, weight_n, {
			pspgu_consts.GU_WEIGHT_8BIT: (8, 1, F8CONV),
			pspgu_consts.GU_WEIGHT_16BIT: (16, 2, F16CONV),
			pspgu_consts.GU_WEIGHT_32BITF: (32, 4, F32CONV),
		},),		
		("texture bits: %d", 0, pspgu_consts.GU_TEXTURE_BITS, 2, {
			pspgu_consts.GU_TEXTURE_8BIT: (8, 1, F8CONV),
			pspgu_consts.GU_TEXTURE_16BIT: (16, 2, F16CONV),
			pspgu_consts.GU_TEXTURE_32BITF: (32, 4, F32CONV),
		},),
		("color format: %s", "unknown", pspgu_consts.GU_COLOR_BITS, 1, {
			pspgu_consts.GU_COLOR_4444: ("16 bits, 4444", 2, HCONV),
			pspgu_consts.GU_COLOR_5551: ("16 bits, 5551", 2, HCONV),
			pspgu_consts.GU_COLOR_5650: ("16 bits, 5650", 2, HCONV),
			pspgu_consts.GU_COLOR_8888: ("32 bits, 8888", 4, ICONV),
		},),
		("normal bits: %d", 0, pspgu_consts.GU_NORMAL_BITS, 3, {
			pspgu_consts.GU_NORMAL_8BIT: (8, 1, F8CONV),
			pspgu_consts.GU_NORMAL_16BIT: (16, 2, F16CONV), 
			pspgu_consts.GU_NORMAL_32BITF: (32, 4, F32CONV),
		},),
		("vertex bits: %d", 0, pspgu_consts.GU_VERTEX_BITS, 3, {
			pspgu_consts.GU_VERTEX_8BIT: (8, 1, F8CONV),
			pspgu_consts.GU_VERTEX_16BIT: (16, 2, F16CONV),
			pspgu_consts.GU_VERTEX_32BITF: (32, 4, F32CONV),
		},),
	)
	
	format_strings = []
	converters = []
	test = bits
	for format, default, mask, count, table in CHECK_ITEMS:
		v = default
		_conv = (0, 0, None)
		for flag, (value, size, converter) in table.iteritems():
			if (bits & mask) == flag:
				_conv = (count, size, converter)
				v = value
				test -= flag
				break
		format_strings.append(format % v)
		converters.append(_conv)
	
	assert test == 0, "unrecognized bits %d" % bits
	return format_strings, converters
		
def dump_to_obj_file(filename, meshes):
	f = open("%s.obj" % filename, "w")
	
	f.write("# List of Vertices\n")
	for vertices in meshes:	
		for vertex in vertices:
			x, y, z = vertex[-3:]
			f.write("v %f %f %f\n" % (x, y, z))
	
	f.write("# List of Normals\n")
	for vertices in meshes:	
		for vertex in vertices:
			nx, ny, nz = vertex[-6:-3]
			f.write("vn %f %f %f\n" % (nx, ny, nz))
		
	f.write("# Face Defination\n")
	base = 0
	for j, vertices in enumerate(meshes):
		f.write("#	 Mesh %d\n" % j)
		for i in xrange(len(vertices)-2):
			f.write("f %d//%d %d//%d %d//%d\n" % (base+i+1,base+i+1,base+i+2,base+i+2,base+i+3,base+i+3))
		base += len(vertices)
		
	f.close()
	
if __name__ == '__main__':
	
	
	if os.path.isdir(sys.argv[1]):
		for mdl_file in glob.glob(os.path.join(sys.argv[1], "*.mdl")):
			log("filename: %s" % mdl_file)
			f = open(mdl_file, "rb")
			data = f.read()
			f.close()
			parse(data, os.path.splitext(mdl_file)[0])
	else:
		
		mdl_file = sys.argv[1]
		log("filename: %s" % mdl_file)
		f = open(mdl_file, "rb")
		data = f.read()
		f.close()
	
		parse(data, os.path.splitext(mdl_file)[0])