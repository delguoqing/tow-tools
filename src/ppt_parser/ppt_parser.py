import sys
import struct
import numpy
import PIL
from PIL import Image
import pixel_conv

GU_PSM_5650 = 0
GU_PSM_5551 = 1
GU_PSM_4444 = 2
GU_PSM_8888 = 3
GU_PSM_T4 = 4
GU_PSM_T8 = 5
GU_PSM_T16 = 6
GU_PSM_T32 = 7
GU_PSM_DXT1 = 8
GU_PSM_DXT3 = 9
GU_PSM_DXT5 = 10

PSM_PALETTE = (GU_PSM_T4,GU_PSM_T8,GU_PSM_T16,GU_PSM_T32)
SIZE_2_FMTSTR = {
	1: "B", 2:"H", 4:"I",
}
PIXEL_SIZE = {
	GU_PSM_5650: 2,
	GU_PSM_5551: 2,
	GU_PSM_4444: 2,
	GU_PSM_8888: 4,
	GU_PSM_T8: 1,
	GU_PSM_T16: 2,	
}

PIXEL_CONV = {
	GU_PSM_5650: pixel_conv.conv5650,
	GU_PSM_5551: pixel_conv.conv5551,
	GU_PSM_4444: pixel_conv.conv4444,
	GU_PSM_8888: pixel_conv.conv8888,
	GU_PSM_T8: pixel_conv.convT8,
	GU_PSM_T16: pixel_conv.convT16,
}

PPT_HEADER = "ppt\x00"
PPC_HEADER = "ppc\x00"

def get_pixel_size(pixel_format):
	if pixel_format in PIXEL_SIZE:
		return PIXEL_SIZE[pixel_format]
	raise Exception("unsupported pixel format!!")

def unswizzle(data, pixel_size, width, height):
	assert len(data) * pixel_size % (16 * 8) == 0
	
	block_height = 8
	block_width = 16 / pixel_size
	
	x_nblock = width / block_width
	y_nblock = height / block_height
	
	dst = [None] * len(data)
	src_offset=  0
	for y_block in xrange(y_nblock):
		for x_block in xrange(x_nblock):
			block_offset = y_block * 8 * width + x_block * block_width
			for i in xrange(8):
				line_offset = block_offset + i * width
				dst[line_offset: line_offset + block_width] = data[src_offset: src_offset + block_width]
				src_offset += block_width
	
	assert len(dst) == len(data), "after unwizzled, not the same size"
	
	return dst
		
def parse(data, out_path="."):
	def _G(offset, fmt):
		fmt_size = struct.calcsize(fmt)
		return struct.unpack(fmt, data[offset: offset + fmt_size])
	
	# check header
	if not data.startswith(PPT_HEADER):
		print "unknown format!"
		return
	
	width, height, format = _G(0x4, "<HHH")
	width, height = _G(0xc, "<HH")
	# get pixel
	pixel_offset = 0x20
	pixel_size = get_pixel_size(format)
	fmt_str = SIZE_2_FMTSTR[pixel_size]
	raw_pixels = _G(pixel_offset, "<"+fmt_str*(width*height))
	raw_pixels = unswizzle(raw_pixels, pixel_size, width, height)
	conv = PIXEL_CONV[format]
	pixels = []
	for raw_pixel in raw_pixels:
		res = conv(raw_pixel)
		if isinstance(res, tuple):
			pixels.extend(res)
		else:
			pixels.append(res)
			
	# color look up
	clut_offset = pixel_offset + pixel_size * (width*height)
	if format in PSM_PALETTE:
		indices = pixels
		pixels = []
		# fetch clut
		magic_code = data[clut_offset: clut_offset + len(PPC_HEADER)]
		if magic_code != PPC_HEADER:
			print "no ppc header!!"
			return
		
		format, num_blocks = _G(clut_offset+0x4, "<HH")
		palette_size = num_blocks * 8
		pixel_size = get_pixel_size(format)
		fmt_str = SIZE_2_FMTSTR[pixel_size]
		raw_pixels = _G(clut_offset+0x10, "<"+fmt_str*palette_size)
		conv = PIXEL_CONV[format]
		clut = map(conv, raw_pixels)
		
		for index in indices:
			pixels.append(clut[index])
		
	# dump pixels to image file
	buf = ""
	for pixel in pixels:
		buf += struct.pack("I", pixel)
	
	image = Image.fromstring("RGBA", (width, height), buf)
	image.save("test.png")
	
if __name__ == '__main__':
	ppt_file = sys.argv[1]
	
	
	fp = open(ppt_file, "rb")
	data = fp.read()
	fp.close()
	
	parse(data)