import os
import sys
import struct
import numpy
import re
import glob
import operator
import fnmatch
import functools
import pspgu_consts

sys.path.append("../ppt_parser")
import ppt_parser

verbers = True

def log(str):
	if verbers:
		print str

def get_primitive_name(self, x):
	d = {}
	for name in ("GU_POINTS", "GU_LINES", "GU_TRIANGLES", "GU_LINE_STRIP",
		"GU_TRIANGLE_STRIP", "GU_TRIANGLE_FAN", "GU_SPRITES"):
		d[name] = getattr(pspgu_consts, name)
	return d[x]
	
def parse_txl(data):
	offset = 0x10
	texture_count, = struct.unpack("<I", data[offset: offset + 0x4])
	offset += 0x4
	
	res = []
	for i in xrange(texture_count):
		txl_name, = struct.unpack("<32s", data[offset: offset + 0x20])
		txl_name = txl_name.rstrip("\x00").replace(".ppt", ".png")
		offset += 0x20
		res.append(txl_name)
		
	return res
		
def get_G(data):
	def _G(offset, fmt):
		fmt_size = struct.calcsize(fmt)
		return struct.unpack(fmt, data[offset: offset + fmt_size])
	return _G
	
def parse(data, txl_data, filename):
	_G = get_G(data)
	def _P(name, value_fmt, locals):
		value_fmt = value_fmt.replace("%", "%%(%s)" % name)
		fmt = "%s = %s" % (name, value_fmt)
		print (fmt % locals)
		
	# check header
	MAGIC_CODE = "MDL\x00"
	magic_code = data[0: len(MAGIC_CODE)]
	if magic_code != MAGIC_CODE:
		raise Exception("unknown file format!")

	# figured out stuff a.t.m
	material_count, = _G(0x1c, "<I")
	texture_count, = _G(0x20, "<I")	# texture_count??
	bone_count, = _G(0x24, "<I")
	block_count, = _G(0x28, "<I")
	
	_P("material_count", "%d", locals())
	_P("texture_count", "%d", locals())
	_P("bone_count", "%d", locals())
	_P("block_count", "%d", locals())

	# unknown values
	p1 = _G(0x2c, "<II")
	txl_ref = _G(0x34, "<" + "I" * texture_count)
	p2 = _G(0x34 + 0x4 * texture_count, "<I")	
	#print
	print "unk part1 " + "(" + ",".join(map(hex, p1)) + ")"
	print "unk part2 " + "(" + ",".join(map(hex, p2)) + ")"
	# guess
	mdl_type = p2[0]
	MDL_TYPE_MODEL = 0x2
	MDL_TYPE_SCENE = 0x103
	MDL_TYPE_MODEL2 = 0x10B
	assert mdl_type in (MDL_TYPE_MODEL, MDL_TYPE_SCENE, MDL_TYPE_MODEL2)

	# material block offset, size
	material_block_size, = _G(0x34 + 0x4 * texture_count + 0x4, "<I")
	material_offset_base = 0x34 + 0x4 * texture_count + 0x4 * 2		
	# single material block size
	assert (material_block_size - 2 * 0x4) % material_count == 0, "[WARNING] matrix block size varies!"
	single_material_block_size = (material_block_size - 2 * 0x4) / material_count
	print
	log("material offset base = 0x%x" % material_offset_base)
	print "material block size = 0x%x" % material_block_size
	
	print "txl ref = ", txl_ref
	
	tot_verts = 0
	
	material_offset = material_offset_base
	materials = []
	for i in xrange(material_count):
		_offset = material_offset

		# material_name		
		if mdl_type == MDL_TYPE_MODEL2:
			material_name = _G(_offset, "<32s")[0].rstrip("\x00")
			_offset += 0x20
			print "material name: %s" % material_name
			
		# Material Matrix
		array = numpy.array(_G(_offset, "<ffffffffffff") + (0, 0, 0, 1))
		_offset += 0x4 * 12
		array.shape = (4, 4)
		matrix = numpy.array(array.copy())
		log("%r" % matrix)
		
		# unknown values
		if mdl_type == MDL_TYPE_SCENE:
			unks2 = _G(_offset, "<IIIIBB")
			_offset += 4 * 0x4 + 2 * 0x1
			material_name = _G(_offset, "<18s")[0].rstrip("\x00")
			_offset += 0x12
			print "material_name: %s" % material_name
			texture_index = unks2[-2]
		elif mdl_type == MDL_TYPE_MODEL:
			unks2 = _G(_offset, "<IIIIIBBBB")
			_offset += 6 * 0x4
			texture_index = unks2[-4]
		elif mdl_type == MDL_TYPE_MODEL2:
			unks2 = _G(_offset, "<iHHBBBB")
			_offset += 3 * 0x4
			texture_index = unks2[-4]
		log("unknown values following: %r\n" % (unks2,))

		materials.append(texture_index)
		material_offset += single_material_block_size
		#assert unks2[3] == txl_ref[i], "txl ref not correct!"
	#	if unks[i+3] != unks2[3]:
	#		print "test failed"
	#		return
	#
	#print "test ok"
	
	# after material block and before bone info
	# offset:				the end of material block
	# 0, <I @ offset: 			unknown
	# 1, <I @ offset + 0x4:	vertices block offset relative to 'offset'
	unk3_offset = material_offset_base + material_count * single_material_block_size
	unks3 = _G(unk3_offset, "<II")
	unks3_ = [unks3[0], ]
	print "unknown values before bones %r" % (unks3_,)
	
	
	# bone info blocks
	bone_offset_base = material_offset_base + material_block_size
	assert unk3_offset + 0x8 == bone_offset_base, "Missing check unknown values"
	
	print
	print "bone_offset_base = 0x%x" % bone_offset_base
	#assert bone_offset_base == material_offset_base + material_block_size, "mat block size wrong!"
	
	bone_names = []
	
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
		
		#assert fvals[:16] == fvals[16:]
		#log("%r" % matrix1)
		bone_names.append(bone_name)

	# vertex blocks
	vertex_block_offset = bone_offset_base + 0xa0 * bone_count
	assert vertex_block_offset == unk3_offset + unks3[1], "Wrong guessing!, 0x%x, 0x%x => 0x%x" % (unk3_offset, unks3[1], vertex_block_offset)
	
	vertex_data = []
	texture_data = []
	prim_types = []
	for _ in xrange(block_count * 2):
		if vertex_block_offset >= len(data):
			break

		vertices, material_index, offset_next, prim_type = parse_vertex_block(_, data, vertex_block_offset, bone_names)
		texture_index = materials[material_index]
		print "texture_index = %d" % texture_index
		vertex_data.append(vertices)
		texture_data.append(texture_index)
		tot_verts += len(vertices)
		vertex_block_offset = offset_next
		prim_types.append(prim_type)
		
	print "\ntot_verts = ", tot_verts
	dump_to_obj_file(filename, vertex_data, texture_data, txl_data, prim_types)

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

# Vertex block header type
HEADER_TYPE0 = 256	# 0, size=9*0x4
HEADER_TYPE1 = 261	# 5, size=11*0x4
HEADER_TYPE2 = 260	# 4, size=7*0x4
HEADER_TYPE3 = 257	# 1, size=4*0x4

def parse_vertex_block_header(data, vertex_block_offset):
	_G = get_G(data)
	header_type, = _G(vertex_block_offset, "<I")
	if header_type == HEADER_TYPE0:
		result = parse_header_type0(data, vertex_block_offset)
	elif header_type == HEADER_TYPE1:
		result = parse_header_type1(data, vertex_block_offset)
	elif header_type == HEADER_TYPE2:
		result = parse_header_type2(data, vertex_block_offset)
	elif header_type == HEADER_TYPE3:
		result = parse_header_type3(data, vertex_block_offset)
	else:
		assert False, "VERTEX BLOCK: unknown header type %d" % header_type
	return result + (header_type, )
	
# type 256: common type for character models
def parse_header_type0(data, vertex_block_offset):
	_G = get_G(data)
	header = _G(vertex_block_offset, "<IIIIHBBbbbbbbbbff")
	block_total_size = header[1]
	vertex_format_bits = header[2]
	vertex_count = header[3]
	material_index = header[4]
	real_weight_count = header[5]
	#assert header[6] == 0, "must be zero!! %d" % header[6]
	related_bone_indices = header[7: 7 + real_weight_count]
	header_size = 9 * 0x4
	raw_header = header[:1] + header[15:]
	prim_type = pspgu_consts.GU_TRIANGLE_STRIP
	
	return block_total_size, vertex_format_bits, vertex_count, material_index, related_bone_indices, raw_header, header_size, prim_type

# type 261: common type for character models(with socket?)	
def parse_header_type1(data, vertex_block_offset):
	_G = get_G(data)
	header = _G(vertex_block_offset, "<IIIIHBBbbbbbbbbff")
	block_total_size = header[1]
	vertex_format_bits = header[2]
	vertex_count = header[3]
	material_index = header[4]
	real_weight_count = header[5]
	#assert header[6] == 0, "must be zero!! %d" % header[6]
	related_bone_indices = header[7: 7 + real_weight_count]
	header_size =  9 * 0x4
	header += _G(vertex_block_offset + header_size, "<ff")
	header_size += 2 * 0x4
	raw_header = header[:1] + header[15:]
	prim_type = pspgu_consts.GU_TRIANGLE_STRIP
	return block_total_size, vertex_format_bits, vertex_count, material_index, related_bone_indices, raw_header, header_size, prim_type
	
# type 260: one of the common types used in scene models(everything except terrain?)
def parse_header_type2(data, vertex_block_offset):
	_G = get_G(data)
	header = _G(vertex_block_offset, "<IIIIIIHH")
	block_total_size = header[1]
	vertex_format_bits = header[2]
	vertex_count = header[3]
	#assert header[4] == 0, "must be zero!! %d" % header[4]
	#assert header[5] == 0x80000000, "ddd"
	print "unknown part = 0x%x, 0x%x" % tuple(header[4:6])
	real_weight_count = 0
	related_bone_indices = []
	header_size = 7 * 0x4
	raw_header = header[:1]
	material_index, flag = header[6:]
	prim_type = pspgu_consts.GU_TRIANGLES
	
	# TODO: This is wrong. Because in scene files, backface-culling is
	# never disabled, single quads are duplicated with normals flipped.
	# ref: http://hi.baidu.com/delguoqing3/item/f3b561f6c76320e10dd1c8ba
	assert flag in (0x0, 0x1), "unknown flag"
	if flag & 0x1:
		sys.stderr.write("disabled back-face culling\n")
	
	return block_total_size, vertex_format_bits, vertex_count, material_index, related_bone_indices, raw_header, header_size, prim_type
	
# type 257: one of the common types used in scene models(terrain?)
def parse_header_type3(data, vertex_block_offset):
	_G = get_G(data)
	header = _G(vertex_block_offset, "<IIII")
	block_total_size = header[1]
	vertex_format_bits = pspgu_consts.GU_VERTEX_16BIT | pspgu_consts.GU_TEXTURE_16BIT | pspgu_consts.GU_NORMAL_16BIT
	# TODO: vertex_format_bits is wrong.
	# vertex order: color > vertex
	# This may be describing a particle
	vertex_count = header[3]
	material_index = header[2]
	related_bone_indices = []
	header_size = 4 * 0x4
	raw_header = header[:1]
	prim_type = pspgu_consts.GU_TRIANGLE_FAN
	
	return block_total_size, vertex_format_bits, vertex_count, material_index, related_bone_indices, raw_header, header_size, prim_type
	
def parse_vertex_block(block_idx, data, vertex_block_offset, bone_names):
	_G = get_G(data)
	
	# log start
	print
	print "VERTEX BLOCK %d, offset=0x%x" % (block_idx, vertex_block_offset)
			
	# parse vertex block header
	result = parse_vertex_block_header(data, vertex_block_offset)
	block_total_size, vertex_format_bits, vertex_count, material_index, \
		related_bone_indices, raw_header, header_size, prim_type, header_type = result
	real_weight_count = len(related_bone_indices)
	
	print "raw header", raw_header
	
	print "vertex count %d" % vertex_count
	print "material index %d" % material_index
	print "vertex format bits = %d" % vertex_format_bits
	print "related bones: ", "|".join([bone_names[related_bone_index] for related_bone_index in related_bone_indices])
		
	format_strings, converters = str_vertex_format(vertex_format_bits)
	total_size = 0
	for count, size, converter in converters:
		total_size += count * size
	
	# need padding
	vertex_padding = 1.0 * (block_total_size - (header_size + vertex_count * total_size)) / vertex_count
	if vertex_padding < 1:
		vertex_padding = 0
	print "vertex_padding:", vertex_padding	
	print "vertex total_size 0x%x" % total_size
	print "\n".join(format_strings)
	print "padding = 0x%x" % vertex_padding
	print "mesh total size: 0x%x" % block_total_size
	assert vertex_padding >= 0, "vertex padding must be unsigned %d" % vertex_padding
	
	# vertices
	vertices_offset_base = vertex_block_offset + header_size

	vertices = []
	for i in xrange(vertex_count):
		vertex_offset = vertices_offset_base + i * (total_size + vertex_padding)
		#log("===>vertex %d: offset = 0x%x" % (i, vertex_offset))

		_offset = vertex_offset
		
		values = []
		if header_type == HEADER_TYPE3:
			vp = _G(_offset, "<fff")
			_offset += 4 * 0x4
			vt = _G(_offset-0x4, "<HH")
			vt = [vt[0]/256.0, vt[1]/256.0]
			values = [None, vt, None, None, vp]
			
			print "what ever:??", vp, vt
		else:
			for count, size, converter in converters:
				_tmp = []
				for j in range(count):
					_tmp.append(converter(data[_offset: _offset + size]))
					_offset += size
				values.append(_tmp)
		
		w, vt, c, n, vp = values
		
		if w:
			#log("w " + (" ".join(map(str,w))))
			
			assert real_weight_count <= len(w), "real weight larger than mem weight n"
			for weight_i in w[real_weight_count:]:
				assert weight_i == 0.0, "weight out of range! %f" % weight_i
				
			w = w[0]
		else:
			w = None
		if vt:
			#log("vt " + (" ".join(map(str,vt))))
			u, v = vt[:2]
		else:
			u, v = None, None
		if c:
			#log("c 0x%08x" % c[0])
			c = c[0]
		else:
			c = None
		if n:
			#log("n " + (" ".join(map(str,n))))
			nx, ny, nz = n[:3]
		else:
			nx, ny, nz = None, None, None
		if vp:
			#log("v " + (" ".join(map(str,vp))))
			x, y, z = vp[:3]
		else:
			x, y, z = None, None, None
		vertices.append((w, u, v, c, nx, ny, nz, x, y, z))

	calc_vertex_block_offset = vertex_block_offset + header_size + vertex_count * (total_size + vertex_padding)
	# 	align to 32bit
	if calc_vertex_block_offset % 0x4 != 0:
		calc_vertex_block_offset += 4 - calc_vertex_block_offset % 0x4
	print "SIZE CHECK:", vertex_block_offset, header_size, vertex_count, total_size, vertex_padding
		
	vertex_block_offset += block_total_size
	print "SIZE CHECK:", vertex_block_offset
	
	if vertex_block_offset != calc_vertex_block_offset:
		sys.stderr.write("Size not match! %d %d\n" % (vertex_block_offset, calc_vertex_block_offset))
		
	if header_type == HEADER_TYPE3:
		print "SURE!!!!!!!!!!!!!!!!!!", vertices
		return vertices, 0, vertex_block_offset, prim_type
		
	return vertices, material_index, vertex_block_offset, prim_type
	
# format vertex format bits to string
def str_vertex_format(bits):
	WEIGHTS_CONSTS = map(pspgu_consts.GU_WEIGHTS, range(1, 9, 1))
	weight_n = WEIGHTS_CONSTS.index(bits & pspgu_consts.GU_WEIGHTS_BITS) + 1
	bits -= pspgu_consts.GU_WEIGHTS(weight_n)
	
	VERTICES_CONSTS = map(pspgu_consts.GU_VERTICES, range(1, 9, 1))
	vertices_n = VERTICES_CONSTS.index(bits & pspgu_consts.GU_VERTICES_BITS) + 1
	bits -= pspgu_consts.GU_VERTICES(vertices_n)
	
	print "weights_n = %d" % weight_n
	print "vertices_n = %d" % vertices_n
	
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
		("vertex bits: %d", 0, pspgu_consts.GU_VERTEX_BITS, vertices_n * 3, {
			pspgu_consts.GU_VERTEX_8BIT: (8, 1, F8CONV),
			pspgu_consts.GU_VERTEX_16BIT: (16, 2, F16CONV),
			pspgu_consts.GU_VERTEX_32BITF: (32, 4, F32CONV),
		},),
	)
	
	print "color bits = 0x%x" % (bits & pspgu_consts.GU_COLOR_BITS)
	
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
		
		if _conv[2] is None:
			print format, "raw bits vaule = 0x%x" % (bits & mask)		
	
	assert test == 0, "unrecognized bits %d" % bits
	return format_strings, converters
		
def dump_to_obj_file(filename, meshes, texture_indices, texture_names, prim_types):
	# mapping duplicate vertices to the same index
	# vertex_map: {vertex_data: index}
	# meshes2: [mesh0_indices, mesh1_indices, mesh2_indices, ...]
	vertex_map = {}
	meshes2 = []
	base = 0
	for vertices in meshes:
		_tmp = []
		for i, vertex in enumerate(vertices):
			if vertex not in vertex_map:
				vertex_map[vertex] = base + i + 1
			_tmp.append(vertex_map[vertex])
		base += len(vertices)
		meshes2.append(_tmp)
			
	f = open(filename, "w")
	
	# referencing material file
	mtl_filename = os.path.split(filename)[1].replace(".obj", ".mtl")
	obj_name = os.path.splitext(mtl_filename)[0]
	f.write("mtllib %s\n" % mtl_filename)
	
	scale_factor = 0.03
	f.write("# List of Vertices\n")
	for vertices in meshes:	
		for vertex in vertices:
			x, y, z = vertex[-3:]
			f.write("v %f %f %f\n" % (x * scale_factor, y * scale_factor, z * scale_factor))
	
	#f.write("# List of Normals\n")
	#for vertices in meshes:	
	#	for vertex in vertices:
	#		nx, ny, nz = vertex[-6:-3]
	#		f.write("vn %f %f %f\n" % (nx, ny, nz))
		
	f.write("# List of Texture Coordinates\n")
	for vertices in meshes:
		for vertex in vertices:
			u, v = vertex[1:3]
			if u is not None and v is not None:
				f.write("vt %f %f\n" % (u, 1.0 - v))
			else:
				f.write("vt 1.0 1.0\n")
			
	f.write("# Face Defination\n")
	f.write("o obj")
	base = 0
	for j, vertices in enumerate(meshes):
		if False and j > 0:
			base += len(vertices)
			continue
		f.write("#	 Mesh %d\n" % j)
		f.write("usemtl mat%d\n" % texture_indices[j])
		f.write("g %s_mesh%d\n" % (obj_name, j))
		f.write("s 1\n")
		
		if prim_types[j] == pspgu_consts.GU_TRIANGLE_STRIP:
		
			for i in xrange(0, len(vertices)-2, 1):
				# use 'meshes2' to look up vertex index
				k1 = meshes2[j][i]
				k2 = meshes2[j][(i+1) % len(vertices)]
				k3 = meshes2[j][(i+2) % len(vertices)]
				#f.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (k1, k1, k1, k2, k2, k2, k3, k3, k3))
				f.write("f %d/%d %d/%d %d/%d\n" % (k1, k1, k2, k2, k3, k3))
		elif prim_types[j] == pspgu_consts.GU_TRIANGLES:
			for i in xrange(0, len(vertices), 3):
				k1 = meshes2[j][i]
				k2 = meshes2[j][i+1]
				k3 = meshes2[j][i+2]
				f.write("f %d/%d %d/%d %d/%d\n" % (k1, k1, k2, k2, k3, k3))
		elif prim_types[j] == pspgu_consts.GU_TRIANGLE_FAN:
			for i in xrange(2, len(vertices)):
				k1 = meshes2[j][0]
				k2 = meshes2[j][i - 1]
				k3 = meshes2[j][i]
				f.write("f %d/%d %d/%d %d/%d\n" % (k1, k1, k2, k2, k3, k3))
		else:
			assert False, "unknown prim type %d" % prim_types[j]
		base += len(vertices)
		
	f.close()
	
	# dump a mtl file
	
	mtl_filename = filename.replace(".obj", ".mtl")
	f = open(mtl_filename, "w")
	for i, texture_name in enumerate(texture_names):
		f.write("newmtl mat%d\n" % i)
		f.write("map_Kd %s\n" % texture_name)
		f.write("\n")
	f.close()
	
def do_file(mdl_file, out_file):
	log("filename: %s" % mdl_file)
	
	# mdl data
	fp = open(mdl_file, "rb")
	data = fp.read()
	fp.close()
	
	# texture name list
	txl_file = mdl_file.replace(".mdl", ".txl")
	fp = open(txl_file, "rb")
	txl_data = parse_txl(fp.read())
	fp.close()
	
	parse(data, txl_data, out_file)
	
	# convert textures
	texture_root = os.path.split(mdl_file)[0]
	out_root = os.path.split(out_file)[0]
	
	for texture_name in txl_data:
		in_file = os.path.join(texture_root, texture_name).replace("png", "ppt")
		out_file = os.path.join(out_root, texture_name)
		ppt_parser.do_file(in_file, out_file)
	
	
if __name__ == '__main__':
	
	if len(sys.argv) == 1:
		print "No input file(*.mdl)!"
	else:
		input = sys.argv[1]
		if os.path.isfile(input):
			mdl_file = input
			if len(sys.argv) > 2:
				out_file = sys.argv[2]
			else:
				out_file = os.path.splitext(mdl_file)[0] + ".obj"
			do_file(mdl_file, out_file)
		else:
			mdl_folder = input
			if len(sys.argv) > 2:
				out_folder = sys.argv[2]
			else:
				out_folder_abs = os.path.abspath(mdl_folder)
				parent_folder, folder = os.path.split(out_folder_abs)
				out_folder = os.path.join(parent_folder, folder+"_objs")
				
			print "out_folder", out_folder
			for root, dirnames, filenames in os.walk(mdl_folder):
				for filename in fnmatch.filter(filenames, "*.mdl"):
					mdl_file = os.path.join(root, filename)
					folder_rel = os.path.relpath(root, mdl_folder)
					out_file = reduce(os.path.join,
						(out_folder, folder_rel, filename.replace(".mdl", ".obj")))
					out_file_folder = os.path.join(out_folder, folder_rel)
					if not os.path.exists(out_file_folder):
						os.makedirs(out_file_folder)
					print mdl_file, out_file
					do_file(mdl_file, out_file)
