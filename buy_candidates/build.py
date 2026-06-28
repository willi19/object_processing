#!/usr/bin/env python3
"""Merge prices, download new product images, write candidates.csv + contact_sheet.html."""
import csv, os, re, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
os.makedirs("images", exist_ok=True)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# --- prices for the original 55 (gathered live) ---
ORIG_PRICE = {
 "wooden_spoon":"22.99","silicone_spatula":"19.99","glass_measuring_cup":"15.85",
 "coffee_mug":"27.99","ceramic_teapot":"26.39","salt_shaker":"12.99","wine_glass":"25.99",
 "travel_mug":"12.99","mason_jar":"14.97","cereal_bowl":"23.99","dinner_plate":"56.99",
 "soup_ladle":"13.79","cheese_grater":"12.99","can_opener":"21.95","garlic_press":"16.99",
 "vegetable_peeler":"11.84","pizza_cutter":"8.99","kitchen_tongs":"9.99","mixing_bowl":"24.99",
 "butter_dish":"13.99","gravy_boat":"25.99","cookie_jar":"34.99","bread_bin":"36.99",
 "napkin_holder":"24.99","fruit_bowl":"49.99","egg_cup":"13.99","honey_dipper":"7.99",
 "coaster":"15.99",
 "trivet":"NA","sponge_holder":"24.99","spice_jar":"NA","olive_oil_bottle":"NA",
 "ketchup_bottle":"NA","cereal_box":"NA","soup_can":"NA","water_bottle":"27.99",
 "thermos_flask":"32.99","tea_kettle":"NA","french_press":"29.99","moka_pot":"44.99",
 "milk_frother":"14.99","yogurt_cup":"NA","butter_knife":"NA","cutting_board":"NA",
 "dish_brush":"NA","measuring_spoons":"11.97","mug_tree":"NA","utensil_holder":"25.99",
 "paper_towel_holder":"24.99","sugar_bowl":"NA","creamer_pitcher":"NA","tea_infuser":"9.99",
 "condiment_squeeze_bottle":"6.74","shaker_bottle":"10.99","napkin_ring":"NA",
}

def curl(url, binary=False):
    args = ["curl","-sL","--compressed","--max-time","45","-A",UA,url]
    if binary:
        args += ["-o","/dev/stdout"]
    r = subprocess.run(args, capture_output=True)
    return r.stdout if binary else r.stdout.decode("utf-8","ignore")

def main_image(html):
    for pat in (r'data-old-hires="(https://[^"]+)"',
                r'"hiRes":"(https://[^"]+)"',
                r'"large":"(https://m\.media-amazon\.com/images/I/[^"]+)"'):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return ""

rows = []  # name,title,price,url,image_url,image_file

# 1) original 55: reuse existing candidates.csv (keeps image_url/image_file), refresh price
with open("candidates.csv") as f:
    for r in csv.DictReader(f):
        r["price"] = ORIG_PRICE.get(r["name"], r.get("price","NA"))
        rows.append([r["name"], r["product_title"], r["price"],
                     r["product_url"], r["image_url"], r["image_file"]])

# 2) new 63: download images, capture image_url
with open("new.tsv") as f:
    for line in f:
        line = line.rstrip("\n")
        if not line:
            continue
        name, url, title, price = line.split("\t")
        imgfile = f"images/{name}.jpg"
        img_url = ""
        if os.path.exists(imgfile) and os.path.getsize(imgfile) > 3000:
            # already have image; still need a url — fetch html for it
            pass
        html = curl(url)
        img_url = main_image(html)
        if img_url and not (os.path.exists(imgfile) and os.path.getsize(imgfile) > 3000):
            data = curl(img_url, binary=True)
            if len(data) > 3000:
                with open(imgfile, "wb") as out:
                    out.write(data)
        ok = os.path.exists(imgfile) and os.path.getsize(imgfile) > 3000
        print(f"{name:24s} price={price:7s} img={'OK' if ok else 'FAIL'}")
        rows.append([name, title, price, url, img_url or "NA",
                     imgfile if ok else "NA"])

# 3) write merged CSV
with open("candidates.csv","w",newline="") as f:
    w = csv.writer(f)
    w.writerow(["name","product_title","price","product_url","image_url","image_file"])
    w.writerows(rows)

# 4) contact sheet
priced = sum(1 for r in rows if r[2] not in ("NA",""))
cards = []
for name,title,price,url,iurl,ifile in rows:
    src = ifile if ifile != "NA" else iurl
    pr = f"${price}" if price not in ("NA","") else "—"
    cards.append(f'''  <a class="card" href="{url}" target="_blank">
    <img loading="lazy" src="{src}" alt="{name}">
    <div class="name">{name}</div>
    <div class="title">{title}</div>
    <div class="price">{pr}</div>
  </a>''')
html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Object Buy Candidates ({len(rows)})</title>
<style>
 body{{font-family:system-ui,Arial,sans-serif;margin:24px;background:#fafafa}}
 h1{{font-size:20px}} .meta{{color:#666;margin-bottom:16px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px}}
 .card{{display:block;background:#fff;border:1px solid #e3e3e3;border-radius:10px;
        padding:10px;text-decoration:none;color:#222;transition:box-shadow .15s}}
 .card:hover{{box-shadow:0 4px 14px rgba(0,0,0,.12)}}
 .card img{{width:100%;height:150px;object-fit:contain;background:#fff}}
 .name{{font-weight:600;font-size:13px;margin-top:8px}}
 .title{{font-size:11px;color:#777;margin-top:3px;height:48px;overflow:hidden}}
 .price{{font-size:14px;font-weight:700;color:#067d62;margin-top:4px}}
</style></head><body>
<h1>Object Buy Candidates</h1>
<div class="meta">{len(rows)} products &middot; {priced} with price &middot; click a card to open its Amazon page</div>
<div class="grid">
{chr(10).join(cards)}
</div></body></html>"""
with open("contact_sheet.html","w") as f:
    f.write(html)

print(f"\nrows={len(rows)}  priced={priced}  -> candidates.csv, contact_sheet.html")
