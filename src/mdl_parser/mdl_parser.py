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
		
def parse(data, txl_data, filename):
	def _G(offset, fmt):
		fmt_size = struct.calcsize(fmt)
		return struct.unpack(fmt, data[offset: offset + fmt_size])
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
	matrix_count, = _G(0x1c, "<I")
	texture_count, = _G(0x20, "<I")	# texture_count??
	bone_count, = _G(0x24, "<I")
	block_count, = _G(0x28, "<I")
	
	#assert matrix_count == texture_count, "not same!! %d %d" % (matrix_count, texture_count)
	
	_P("matrix_count", "%d", locals())
	_P("texture_count", "%d", locals())
	_P("bone_count", "%d", locals())
	_P("block_count", "%d", locals())
	
	# matrix
	matrix_offset_base = 0x4c + (texture_count - 0x4) * 0x4

	
	unks = _G(0x2c, "<"+"I"*((matrix_offset_base-0x2c)/0x4))
	txl_ref = unks[2: 2 + texture_count]
	
	p1 = unks[:2]
	p2 = unks[2 + texture_count:]
	
	#print
	print "unk part1 %r" % (p1, )
	print "unk_part2 %r" % (p2, )
	
	#assert p1[0] == 1 and p2[0] == 2, "%d, %d" % (p1[0], p2[0])
	#assert p1[1] == texture_count * 4 + 8, "just guessing~!"
	
	matrix_block_size = p2[1]
	
	
	print
	log("matrix offset base = 0x%x" % matrix_offset_base)
	print "matrix block size = 0x%x" % matrix_block_size
	
	print "txl ref = ", txl_ref
	
	matrix_offset = matrix_offset_base
	for i in xrange(texture_count):
	
		#if i >= texture_count - matrix_count:
		#	print "extended:", _G(matrix_offset, "<IH")
		#	material_name, = _G(matrix_offset + 0x6, "<12s")
		#	material_name = material_name.rstrip("\x00")
		#	print "mat name: %s" % material_name
		#	
		#	matrix_offset += 18
			
		array = numpy.array(_G(matrix_offset, "<ffffffffffff") + (0, 0, 0, 1))
		array.shape = (4, 4)
		matrix = numpy.array(array.copy())
		log("%r" % matrix)
		unk_offset = matrix_offset + 12*0x4
		unks2 = _G(unk_offset, "<iHHBBBB")
		log("unknown values following: %r\n" % (unks2,))

		matrix_offset += 0x3c
		#assert unks2[3] == txl_ref[i], "txl ref not correct!"
	#	if unks[i+3] != unks2[3]:
	#		print "test failed"
	#		return
	#
	#print "test ok"
	
	# after texture matrix and before bone info
	unk_offset = matrix_offset_base + matrix_count * (12+3) * 0x4
	unks3 = _G(unk_offset, "<II")
	print "unknown values before bones %r" % (unks3,)
	
	# bone info blocks
	#bone_offset_base = unk_offset + 0x8
	bone_offset_base = matrix_offset_base + matrix_block_size
	print
	print "bone_offset_base = 0x%x" % bone_offset_base
	#assert bone_offset_base == matrix_offset_base + matrix_block_size, "mat block size wrong!"
	
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
	vertex_data = []
	texture_data = []
	for _ in xrange(block_count):
		if vertex_block_offset >= len(data):
			break
		print
		print "VERTEX BLOCK %d, offset=0x%x" % (_, vertex_block_offset)
		# vertex block header
		header = _G(vertex_block_offset, "<IIIIHBBbbbbbbbbff")
		
		block_total_size = header[1]
		vertex_format_bits = header[2]
		vertex_count = header[3]
		texture_index = header[4]
		real_weight_count = header[5]
		#assert header[6] == 0, "must be zero!! %d" % header[6]
		related_bone_indices = header[7: 7 + real_weight_count]
		
		header_size = 9 * 0x4
		if header[0] & 0x1:	# ????
			sys.stderr.write("special bit")
			header += _G(vertex_block_offset + header_size, "<ff")
			header_size += 2 * 0x4
			
		#bone_bits_values = header[7:11]
		#for bone_bits_value in bone_bits_values:
		#	print bin(bone_bits_value)
		
		raw_header = header[:1] + header[15:]
		print "raw header", raw_header
		
		print "vertex count %d" % vertex_count
		print "texture index %d" % texture_index
		texture_data.append(texture_index)
		print "vertex format bits = %d" % vertex_format_bits
		print "related bones: ", "|".join([bone_names[related_bone_index] for related_bone_index in related_bone_indices])
		
		
		format_strings, converters = str_vertex_format(vertex_format_bits)
		total_size = 0
		for count, size, converter in converters:
			total_size += count * size
		print "vertex total_size 0x%x" % total_size
		print "\n".join(format_strings)
		
		print "mesh total size: %d" % block_total_size
		
		# vertices
		vertices = []
		vertices_offset_base = vertex_block_offset + header_size
		for i in xrange(vertex_count):
			vertex_offset = vertices_offset_base + i * total_size
			#log("===>vertex %d: offset = 0x%x" % (i, vertex_offset))
	
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
			
		vertex_data.append(vertices)
		vertex_block_offset += header_size + vertex_count * total_size
		
		# align to 32bit
		if vertex_block_offset % 0x4 != 0:
			vertex_block_offset += 4 - vertex_block_offset % 0x4
	
	dump_to_obj_file(filename, vertex_data, texture_data, txl_data)

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
		
def dump_to_obj_file(filename, meshes, texture_indices, texture_names):
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
	
	f.write("# List of Vertices\n")
	for vertices in meshes:	
		for vertex in vertices:
			x, y, z = vertex[-3:]
			f.write("v %f %f %f\n" % (x, y, z))
	
	#f.write("# List of Normals\n")
	#for vertices in meshes:	
	#	for vertex in vertices:
	#		nx, ny, nz = vertex[-6:-3]
	#		f.write("vn %f %f %f\n" % (nx, ny, nz))
		
	f.write("# List of Texture Coordinates\n")
	for vertices in meshes:
		for vertex in vertices:
			u, v = vertex[1:3]
			f.write("vt %f %f\n" % (u, 1.0 - v))
			
	f.write("# Face Defination\n")
	f.write("o obj")
	base = 0
	for j, vertices in enumerate(meshes):
		if False and j > 1:
			base += len(vertices)
			continue
		f.write("#	 Mesh %d\n" % j)
		f.write("usemtl mat%d\n" % texture_indices[j])
		f.write("g %s_mesh%d\n" % (obj_name, j))
		f.write("s 1\n")

		for i in xrange(0, len(vertices)-2, 1):
			# use 'meshes2' to look up vertex index
			k1 = meshes2[j][i]
			k2 = meshes2[j][(i+1) % len(vertices)]
			k3 = meshes2[j][(i+2) % len(vertices)]
			#f.write("f %d/%d/%d %d/%d/%d %d/%d/%d\n" % (k1, k1, k1, k2, k2, k2, k3, k3, k3))
			f.write("f %d/%d %d/%d %d/%d\n" % (k1, k1, k2, k2, k3, k3))
			
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
