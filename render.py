GAME_VERSION = "1.3.3.1"

def get_concat_h_repeat(im, column):
    dst = Image.new('RGB', (im.width * column, im.height))
    for x in range(column):
        dst.paste(im, (x * im.width, 0))
    return dst

def get_concat_v_repeat(im, row):
    dst = Image.new('RGB', (im.width, im.height * row))
    for y in range(row):
        dst.paste(im, (0, y * im.height))
    return dst

def get_concat_tile_repeat(im, row, column):
    dst_h = get_concat_h_repeat(im, column)
    return get_concat_v_repeat(dst_h, row)

def argb_split(x):
	return (x & 0xFFFFFFFF).to_bytes(4, 'big')
def load_image(imagename):
	if imagename not in images:
		images[imagename] = Image.open(requests.get(IMAGE_URL + imagename + ".png", stream=True).raw)
	return images[imagename]

from PIL import Image, ImageFilter, ImageDraw
import json
import xml
import requests
import requests_cache
from bs4 import BeautifulSoup
import untangle
import base64
import io

skinfiles = set(["players"])
textilefiles = set()

requests_cache.install_cache(backend="sqlite")

XML_URL = "https://www.haizor.net/rotmg/assets/production/xml/"
IMAGE_URL = "https://www.haizor.net/rotmg/assets/production/sheets/"

soup = BeautifulSoup(requests.get(XML_URL).content, "html.parser")
images = {}
render = Image.new("RGBA", (45 * 100 + 5, 45 * 100 + 5))
renderdraw = ImageDraw.Draw(render)
imgx = 2 #skip Empty and Unknown slots
imgy = 0
allblack = Image.new("RGBA", (40, 40), "BLACK")

items = {
     -1: ["Empty Slot", 0, -1, 5, 5, 0, 0, 0, False, 0],
      0x0: ["Unknown Item", 0, -1, 50, 5, 0, 0, 0, False, 0],
}
classes = {}
skins = {}
petAbilities = {}
textures = {}

render.paste(Image.open("error.png"), (50, 5))

for a in soup.find_all("a"):
	href = a.get("href")
	if href is not None:
		#print(">>>", href)
		try:
			xmldata = requests.get(XML_URL + href).content.decode("utf-8")
			#if "playerskins_mask" in xmldata:
				#print(href)
			data = untangle.parse(xmldata)
		except xml.sax._exceptions.SAXParseException:
			#print("       bad")
			continue
		datatype = dir(data)[0]
		if datatype == "Objects" and "Object" in dir(data.Objects):
			for obj in data.Objects.Object:
				if "Class" not in dir(obj):
					continue
				if obj.Class.cdata == "Player":
					baseStats = [
						int(obj.MaxHitPoints.cdata),
						int(obj.MaxMagicPoints.cdata),
						int(obj.Attack.cdata),
						int(obj.Defense.cdata),
						int(obj.Speed.cdata),
						int(obj.Dexterity.cdata),
						int(obj.HpRegen.cdata),
						int(obj.MpRegen.cdata),
					]
					averages = {}
					for f in obj.LevelIncrease:
						averages[f.cdata] = (int(f["min"]) + int(f["max"])) / 2 * 19
					avgs = [
						averages["MaxHitPoints"],
						averages["MaxMagicPoints"],
						averages["Attack"],
						averages["Defense"],
						averages["Speed"],
						averages["Dexterity"],
						averages["HpRegen"],
						averages["MpRegen"],
					]
					avgs = [x+y for x,y in zip(baseStats, avgs)]
					if obj["type"].startswith("0x"):
						key = int(obj["type"][2:], 16)
					else:
						1/0
					classes[key] = [
						obj["id"],
						baseStats,
						avgs,
						[
							int(obj.MaxHitPoints["max"]),
							int(obj.MaxMagicPoints["max"]),
							int(obj.Attack["max"]),
							int(obj.Defense["max"]),
							int(obj.Speed["max"]),
							int(obj.Dexterity["max"]),
							int(obj.HpRegen["max"]),
							int(obj.MpRegen["max"]),
						],
						[int(x) for x in obj.SlotTypes.cdata.split(",")[:4]]
					]
					if obj.AnimatedTexture.Index.cdata.startswith('0x'):
						index = int(obj.AnimatedTexture.Index.cdata[2:], 16)
					else:
						index = int(obj.AnimatedTexture.Index.cdata)
					skins[key] = [
						obj["id"],
						index,
						False,
						obj.AnimatedTexture.File.cdata,
						key,
					]
				if obj.Class.cdata == "Skin" or "Skin" in dir(obj):
					if not obj.PlayerClassType.cdata.startswith('0x'):
						1/0
					if not obj["type"].startswith('0x'):
						1/0
					if obj.AnimatedTexture.Index.cdata.startswith('0x'):
						index = int(obj.AnimatedTexture.Index.cdata[2:], 16)
					else:
						index = int(obj.AnimatedTexture.Index.cdata)
					skins[int(obj["type"][2:], 16)] = [
						obj["id"],
						index,
						"16" in obj.AnimatedTexture.File.cdata,
						obj.AnimatedTexture.File.cdata,
						int(obj.PlayerClassType.cdata[2:], 16)
					]
					skinfiles.add(obj.AnimatedTexture.File.cdata)
				elif obj.Class.cdata == "PetAbility" or "PetAbility" in dir(obj):
					if obj["type"].startswith("0x"):
						petAbilities[int(obj["type"][2:], 16)] = obj["id"]
					else:
						1/0
				if obj.Class.cdata == "Dye":
					if "Tex1" in dir(obj):
						key = obj.Tex1.cdata
						offs = 0
					elif "Tex2" in dir(obj):
						key = obj.Tex2.cdata
						offs = 2
					else:
						1/0
					if key.startswith("0x"):
						key = int(key[2:], 16)
					else:
						1/0 #key = int(key)
					data = textures.get(key, [None]*4)
					data[offs+0] = obj["id"]
					if obj["type"].startswith("0x"):
						data[offs+1] = int(obj["type"][2:], 16)
					else:
						1/0
					textures[key] = data
				if obj.Class.cdata == "Equipment" or obj.Class.cdata == "Dye":
					if "BagType" not in dir(obj):
						continue #Procs are Equipment too for some reason!??
					if "DisplayId" in dir(obj) and obj.Class.cdata != "Dye":
						id = obj.DisplayId.cdata
					else:
						id = obj["id"]
					#print(id)
					type = obj["type"]
					if type.startswith("0x"):
						type = int(type[2:], 16)
					else:
						type = int(type)
					if "Tier" in dir(obj):
						tier = int(obj.Tier.cdata)
					else:
						tier = -1
					if "XPBonus" in dir(obj):
						xp = int(obj.XPBonus.cdata)
					else:
						xp = 0
					if "feedPower" in dir(obj):
						fp = int(obj.feedPower.cdata)
					else:
						fp = 0
					slot = int(obj.SlotType.cdata)
					soulbound = "Soulbound" in dir(obj)
					utst = 0
					if "setName" in repr(obj):
						utst = 2
					elif (slot >= 1 and slot <= 9) or (slot >= 11 and slot <= 25):
						if soulbound and tier == -1:
							utst = 1

					if "Texture" in dir(obj):
						imagename = obj.Texture.File.cdata
						imageindex = obj.Texture.Index.cdata
					else:
						imagename = obj.AnimatedTexture.File.cdata
						imageindex = obj.AnimatedTexture.Index.cdata
					if imageindex.startswith("0x"):
						imageindex = int(imageindex[2:], 16)
						normalIndex = True
					else:
						imageindex = int(imageindex)
						normalIndex = False
					img = load_image(imagename)

					# TODO: manifest.xml has this data, but this seems alright for now
					imgTileSize = 8
					if "16" in imagename or imagename == "petsDivine":
						imgTileSize = 16
					elif "32" in imagename:
						imgTileSize = 32

					if normalIndex:
						srcw = img.size[0] / imgTileSize
						srcx = imgTileSize * (imageindex % srcw)
						srcy = imgTileSize * (imageindex // srcw)
					elif imagename == "playerskins":
						srcx = 0
						srcy = 3 * imgTileSize * imageindex
					else:
						srcx = 0
						srcy = imgTileSize * imageindex

					icon = img.crop((srcx, srcy, srcx+imgTileSize, srcy+imgTileSize)).resize((40, 40), Image.NEAREST)
					edges = icon.split()[-1].filter(ImageFilter.MaxFilter(3))
					shadow = edges.filter(ImageFilter.BoxBlur(7)).point(lambda alpha: alpha // 2)
					render.paste(allblack, (imgx * 45 + 5, imgy * 45 + 5), shadow)
					render.paste(allblack, (imgx * 45 + 5, imgy * 45 + 5), edges)
					icon = icon.crop((1, 1, 39, 39))
					render.paste(icon, (imgx * 45 + 5 + 1, imgy * 45 + 5 + 1), icon)

					if "Mask" in dir(obj):
						maskname = obj.Mask.File.cdata
						maskindex = obj.Mask.Index.cdata
						if maskindex.startswith("0x"):
							maskindex = int(maskindex[2:], 16)
						else:
							print(href,id)
							1/0
						img = load_image(maskname)
						srcw = img.size[0] / imgTileSize
						srcx = imgTileSize * (maskindex % srcw)
						srcy = imgTileSize * (maskindex // srcw)
						mask = img.crop((srcx, srcy, srcx+imgTileSize, srcy+imgTileSize)).resize((40, 40), Image.NEAREST)
						if "Tex1" in dir(obj) and "Tex2" in dir(obj):
							print(href,id)
							1/0
						elif "Tex1" in dir(obj):
							tex = obj.Tex1.cdata
						elif "Tex2" in dir(obj):
							tex = obj.Tex2.cdata
						else:
							print(href,id)
							1/0
						if tex.startswith("0x"):
							tex = int(tex[2:], 16)
						else:
							print(href,id)
							1/0
						a,r,g,b = argb_split(tex)
						if a == 1: #color
							img = Image.new("RGB", (40, 40), (r,g,b))
						else: #texture
							if r > 0 or g > 0:
								print(href,id)
								1/0
							textilefiles.add(a)
							img = load_image(f"textile{a}x{a}")
							srcw = img.size[0] / a
							srcx = a * (b % srcw)
							srcy = a * (b // srcw)
							img = img.crop((srcx, srcy, srcx+a, srcy+a))
							img = get_concat_tile_repeat(img, 10, 10)
							img = img.crop((0, 0, 40, 40))
						render.paste(allblack, (imgx * 45 + 5, imgy * 45 + 5), mask)
						render.paste(img, (imgx * 45 + 5, imgy * 45 + 5), mask.split()[0])
						render.paste(img, (imgx * 45 + 5, imgy * 45 + 5), mask.split()[1])

					if "Quantity" in dir(obj):
						num = obj.Quantity.cdata
						renderdraw.text((imgx * 45 + 5 + 3 - 1, imgy * 45 + 5 + 3 - 1), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 - 1, imgy * 45 + 5 + 3 - 0), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 - 1, imgy * 45 + 5 + 3 + 1), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 - 0, imgy * 45 + 5 + 3 - 1), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 - 0, imgy * 45 + 5 + 3 + 1), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 + 1, imgy * 45 + 5 + 3 - 1), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 + 1, imgy * 45 + 5 + 3 - 0), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 + 1, imgy * 45 + 5 + 3 + 1), num, fill="#000")
						renderdraw.text((imgx * 45 + 5 + 3 - 0, imgy * 45 + 5 + 3 - 0), num, fill="#fff")

					items[type] = [id, slot, tier, imgx * 45 + 5, imgy * 45 + 5, xp, fp, int(obj.BagType.cdata), soulbound, utst]
					imgx += 1
					if imgx >= 100:
						imgx = 0
						imgy += 1
						if imgy >= 100:
							1/0

render = render.crop((0, 0, 45 * 100 + 5, 45 * (imgy + 1) + 5))

from datetime import datetime
now = datetime.now().strftime("%Y%m%d-%H%M%S")

with open("constants.js", "w") as fh:
	fh.write("// Generated with https://github.com/BR-/muledump-render\n\n")
	fh.write(f'rendersVersion = "renders-{now}-{GAME_VERSION}";\n\n')
	fh.write('//   type: ["id", SlotType, Tier, x, y, FameBonus, feedPower, BagType, Soulbound, UT/ST],\n')
	fh.write("items = {\n")
	for itemid, itemdata in sorted(items.items()):
		if itemid == -1:
			fh.write(f"  '{itemid}': {itemdata},\n".replace("False,", "false,").replace("True,", "true,"))
		else:
			fh.write(f"  {itemid}: {itemdata},\n".replace("False,", "false,").replace("True,", "true,"))
	fh.write("};\n\n")
	fh.write('//   type: ["id", base, averages, maxes, slots]\n')
	fh.write("classes = {\n")
	for classid, classdata in sorted(classes.items()):
		fh.write(f"  {classid}: {classdata},\n")
	fh.write("};\n\n")
	fh.write('//   type: ["id", index, 16x16, "sheet", class]\n')
	fh.write("skins = {\n")
	for skinid, skindata in sorted(skins.items()):
		fh.write(f"  {skinid}: {skindata},\n".replace("False,", "false,").replace("True,", "true,"))
	fh.write("};\n\n")
	fh.write('//   type: "id"\n')
	fh.write("petAbilities = {\n")
	for petAbilId, petAbilName in sorted(petAbilities.items()):
		fh.write(f'  {petAbilId}: "{petAbilName}",\n')
	fh.write("};\n\n")
	fh.write('//   texId: ["clothing id", clothing type, "accessory id", accessory type]\n')
	fh.write("textures = {\n")
	for textureId, textureData in sorted(textures.items()):
		fh.write(f"  {textureId}: {textureData},\n")
	fh.write("}\n")

render.save("renders.png", "PNG", quality=100)

with open("sheets.js", "w") as fh:
	fh.write("textiles = {\n")
	for textilefile in sorted(textilefiles):
		textiledata = base64.b64encode(requests.get(IMAGE_URL + f"textile{textilefile}x{textilefile}.png").content).decode()
		fh.write(f"  {textilefile}: 'data:image/png;base64,{textiledata}',\n")
	fh.write("};\n\n")
	fh.write("skinsheets = {\n")
	for skinfile in sorted(skinfiles):
		skindata = base64.b64encode(requests.get(IMAGE_URL + skinfile + ".png").content).decode()
		fh.write(f"  {skinfile}: 'data:image/png;base64,{skindata}',\n")
		skindata = base64.b64encode(requests.get(IMAGE_URL + skinfile + "_mask.png").content).decode()
		fh.write(f"  {skinfile}Mask: 'data:image/png;base64,{skindata}',\n")
	fh.write("};\n\n")

	buf = io.BytesIO()
	render.save(buf, "PNG", quality=100)
	renderdata = base64.b64encode(buf.getvalue()).decode()
	fh.write(f"renders = 'data:image/png;base64,{renderdata}';\n")
