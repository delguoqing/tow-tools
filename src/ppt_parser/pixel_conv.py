def make_conv16bit(bits):
	def conv16bit(pixel):
		res = 0
		for i in xrange(4):
			if bits[i] != 0:
				cbits = ((1 << (bits[i]+1))-1)
				vi = (pixel >> sum(bits[i+1:])) & cbits
				v = int(255.0 * vi / cbits)
			else:
				v = 0xFF
			res |= (v << ((3-i)*8))
		return res
	return conv16bit

conv5650 = make_conv16bit((5,6,5,0))
conv5551 = make_conv16bit((5,5,5,1))
conv4444 = make_conv16bit((4,4,4,4))
conv8888 = lambda pixel: pixel
convT8 = lambda pixel: pixel
convT16 = lambda pixel: pixel