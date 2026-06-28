#!/usr/bin/env bash
# Read sources.tsv (name<TAB>url<TAB>title), fetch each Amazon page, extract the
# main product image + price, download the image as images/<name>.jpg, and write candidates.csv.
set -u
cd "$(dirname "$0")"
mkdir -p images
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# CSV header
{
  printf 'name,product_title,price,product_url,image_url,image_file\n'
} > candidates.csv

n=0; ok_img=0
while IFS=$'\t' read -r name url title; do
  [ -z "${name:-}" ] && continue
  n=$((n+1))
  html=$(curl -sL --compressed --max-time 40 -A "$UA" "$url")
  # main product image: prefer data-old-hires, else first hiRes JSON field
  img=$(printf '%s' "$html" | grep -aoE 'data-old-hires="https://[^"]+"' | head -1 | sed -E 's/.*"(https:[^"]+)"/\1/')
  [ -z "$img" ] && img=$(printf '%s' "$html" | grep -aoE '"hiRes":"https://[^"]+"' | head -1 | sed -E 's/.*"(https:[^"]+)"/\1/')
  [ -z "$img" ] && img=$(printf '%s' "$html" | grep -aoE '"large":"https://m\.media-amazon\.com/images/I/[^"]+"' | head -1 | sed -E 's/.*"(https:[^"]+)"/\1/')
  # price: first apex a-price (whole + fraction)
  price=$(printf '%s' "$html" | grep -aoE 'a-price-whole">[0-9,]+</span><span class="a-price-decimal">.</span><span class="a-price-fraction">[0-9]{2}' | head -1 | sed -E 's/.*a-price-whole">([0-9,]+).*fraction">([0-9]{2}).*/\1.\2/')
  [ -z "$price" ] && price=$(printf '%s' "$html" | grep -aoE '"priceAmount":[0-9]+\.[0-9]{2}' | head -1 | sed -E 's/.*://')

  imgfile=""
  if [ -n "$img" ]; then
    if curl -sL --compressed --max-time 40 -A "$UA" "$img" -o "images/${name}.jpg" && [ -s "images/${name}.jpg" ]; then
      imgfile="images/${name}.jpg"; ok_img=$((ok_img+1))
    fi
  fi
  # CSV-escape title (wrap in quotes, double internal quotes)
  esc_title=${title//\"/\"\"}
  printf '%s,"%s",%s,%s,%s,%s\n' "$name" "$esc_title" "${price:-NA}" "$url" "${img:-NA}" "${imgfile:-NA}" >> candidates.csv
  printf '[%2d] %-24s price=%-8s img=%s\n' "$n" "$name" "${price:-NA}" "${imgfile:-FAILED}"
done < sources.tsv

echo "----"
echo "rows: $n  images downloaded: $ok_img"
