"""
generate_meijer_crosssell.py
Generates data/Meijer_crosssell.csv with logical grocery cross-sell / upsell / similar
relationships for all 145 Meijer products.

RELATION_TYPE values:
  crosssell  – complementary products (chips + dip, pizza + soda, cereal + milk)
  upsell     – premium / larger version of the same product
  similar    – same sub-category alternatives

Then creates SAP_MEIJER_CROSSSELL_V1 in SAP HANA and loads the data.

Run: .\\venv\\Scripts\\python.exe generate_meijer_crosssell.py
"""

import csv, os, sys

OUTPUT_CSV = os.path.join("data", "Meijer_crosssell.csv")

# ─── Helper ──────────────────────────────────────────────────────────────────
rows = []
def add(product_id, related_id, relation_type, display_order):
    rows.append((str(product_id), str(related_id), relation_type, display_order))

# ─────────────────────────────────────────────────────────────────────────────
# ICE CREAM  (300101)
# ─────────────────────────────────────────────────────────────────────────────
# Vanilla Ice Cream  →  waffle cones, cookies, sorbet
add("200001","200009","crosssell",1)   # Waffle Cones Kit
add("200001","500022","crosssell",2)   # Oreo Cookies
add("200001","200006","similar",  3)   # Mango Sorbet
add("200001","200007","similar",  4)   # Frozen Yogurt Vanilla
add("200001","200008","upsell",   5)   # Party Size

# Chocolate Ice Cream Pints  →  waffle cones, cookies
add("200002","200009","crosssell",1)
add("200002","500021","crosssell",2)   # Chocolate Chip Cookies
add("200002","200001","similar",  3)
add("200002","200008","upsell",   4)

# Dairy-Free Ice Cream  →  similar dairy-free, waffle cones
add("200003","200006","similar",  1)
add("200003","200004","similar",  2)
add("200003","200009","crosssell",3)

# Strawberry Ice Pops  →  similar frozen treats
add("200004","200003","similar",  1)
add("200004","200005","similar",  2)
add("200004","200009","crosssell",3)

# Ice Cream Sandwiches  →  cookies, milk
add("200005","500022","crosssell",1)
add("200005","600001","crosssell",2)   # Whole Milk
add("200005","200001","similar",  3)

# Mango Sorbet  →  similar, waffle cones
add("200006","200001","similar",  1)
add("200006","200003","similar",  2)
add("200006","200009","crosssell",3)

# Frozen Yogurt Vanilla  →  granola, milk
add("200007","730008","crosssell",1)   # Granola Breakfast Blend
add("200007","600001","crosssell",2)
add("200007","200001","similar",  3)

# Party Size Cookie Dough  →  waffle cones, soda
add("200008","200009","crosssell",1)
add("200008","610001","crosssell",2)   # Cola 12-Pack
add("200008","200002","similar",  3)

# Waffle Cones Kit  →  ice cream
add("200009","200001","crosssell",1)
add("200009","200002","crosssell",2)
add("200009","200006","crosssell",3)

# ─────────────────────────────────────────────────────────────────────────────
# FROZEN MEALS  (300201 – 300209)
# ─────────────────────────────────────────────────────────────────────────────
# Family-Size Lasagna  →  cola, garlic bread, salad
add("400001","610008","crosssell",1)   # MultiServe Cola 2L
add("400001","710001","crosssell",2)   # Classic White Bread
add("400001","400002","similar",  3)   # Chicken Alfredo

# Chicken Alfredo Single-Serve  →  soda, similar
add("400002","610003","crosssell",1)   # Lemon Lime Soda
add("400002","400001","similar",  2)
add("400002","400006","upsell",   3)   # Healthy Living Meal

# Beef Skillet Meal  →  soda, bread
add("400003","610008","crosssell",1)
add("400003","710001","crosssell",2)
add("400003","400001","similar",  3)

# Chicken Tikka Masala  →  bread, water
add("400004","710001","crosssell",1)
add("400004","620002","crosssell",2)   # Purified Water 1L
add("400004","400006","similar",  3)

# Chicken Pot Pie  →  cola, similar
add("400005","610006","crosssell",1)   # Root Beer
add("400005","400001","similar",  2)
add("400005","400009","similar",  3)

# Healthy Living Meal  →  water, yogurt
add("400006","620002","crosssell",1)
add("400006","700003","crosssell",2)   # Greek Yogurt Plain
add("400006","400002","similar",  3)

# Taquitos  →  salsa, soda
add("400007","500107","crosssell",1)   # Mild Salsa Dip
add("400007","610003","crosssell",2)
add("400007","400008","similar",  3)

# Pocket Sandwich  →  soda, chips
add("400008","610002","crosssell",1)   # Zero Sugar Cola
add("400008","500101","crosssell",2)   # Potato Chips
add("400008","400007","similar",  3)

# Chicken Nuggets Kids Meal  →  ketchup/dip, juice/soda
add("400009","610004","crosssell",1)   # Orange Spark Soda
add("400009","500101","crosssell",2)
add("400009","400008","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# FROZEN PIZZA  (333300)
# ─────────────────────────────────────────────────────────────────────────────
# Single Serve Pizza  →  upsell to Pepperoni, cola
add("500001","500003","upsell",   1)
add("500001","610002","crosssell",2)
add("500001","500002","similar",  3)

# Pizza Snacks  →  cola, dip
add("500002","610001","crosssell",1)
add("500002","500107","crosssell",2)
add("500002","500001","similar",  3)

# Pepperoni Pizza  →  cola, chips
add("500003","610001","crosssell",1)
add("500003","500109","crosssell",2)   # Pringles
add("500003","500004","similar",  3)

# Meat Pizza  →  cola 12-pack, chips
add("500004","610001","crosssell",1)
add("500004","500101","crosssell",2)
add("500004","500005","similar",  3)

# Supreme Pizza  →  cola, chips, similar
add("500005","610008","crosssell",1)
add("500005","500109","crosssell",2)
add("500005","500003","similar",  3)

# Cheese Pizza  →  root beer, crackers
add("500006","610006","crosssell",1)
add("500006","500012","crosssell",2)   # Ritz Classic Crackers
add("500006","500003","similar",  3)

# Veggie Pizza  →  sparkling water, salad dressing concept
add("500007","620003","crosssell",1)   # Sparkling Mineral Water
add("500007","500106","crosssell",2)   # Baked Veggie Straws
add("500007","500006","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# CHIPS  (400101)
# ─────────────────────────────────────────────────────────────────────────────
add("500101","500107","crosssell",1)   # Salsa Dip
add("500101","610003","crosssell",2)   # Lemon Lime Soda
add("500101","500110","similar",  3)   # Lays Classic
add("500101","500109","similar",  4)   # Pringles

add("500102","500107","crosssell",1)   # Salsa
add("500102","610004","crosssell",2)   # Orange Soda
add("500102","500101","similar",  3)
add("500102","500105","similar",  4)

add("500103","500107","crosssell",1)
add("500103","610005","crosssell",2)   # Ginger Ale
add("500103","500102","similar",  3)

add("500104","620004","crosssell",1)   # Soda Water
add("500104","500101","similar",  2)
add("500104","500109","similar",  3)

add("500105","500107","crosssell",1)
add("500105","610006","crosssell",2)
add("500105","500101","similar",  3)

add("500106","620006","crosssell",1)   # Lemon Enhanced Water
add("500106","500104","similar",  2)
add("500106","500103","similar",  3)

add("500107","500101","crosssell",1)   # Salsa pairs with chips
add("500107","500102","crosssell",2)
add("500107","500103","crosssell",3)

add("500108","500107","crosssell",1)
add("500108","610003","crosssell",2)
add("500108","500101","similar",  3)

add("500109","610001","crosssell",1)
add("500109","500107","crosssell",2)
add("500109","500101","similar",  3)
add("500109","500110","similar",  4)

add("500110","500107","crosssell",1)
add("500110","610003","crosssell",2)
add("500110","500101","similar",  3)
add("500110","500109","similar",  4)

# ─────────────────────────────────────────────────────────────────────────────
# CRACKERS  (400102)
# ─────────────────────────────────────────────────────────────────────────────
add("500011","600015","crosssell",1)   # Swiss Sliced Cheese
add("500011","600018","crosssell",2)   # Cream Cheese Spread
add("500011","500012","similar",  3)

add("500012","600018","crosssell",1)
add("500012","600016","crosssell",2)   # American Sliced Cheese
add("500012","500013","similar",  3)

add("500013","600015","crosssell",1)
add("500013","600017","crosssell",2)   # Cheese Cubes
add("500013","500012","similar",  3)

add("500014","600017","crosssell",1)
add("500014","500012","similar",  2)

add("500015","600018","crosssell",1)
add("500015","500012","similar",  2)

add("500016","620006","crosssell",1)   # Lemon Water
add("500016","500017","similar",  2)

add("500017","600001","crosssell",1)   # Whole Milk for s'mores
add("500017","500012","similar",  2)

add("500018","620003","crosssell",1)   # Sparkling Water
add("500018","500012","similar",  2)

add("500019","600015","crosssell",1)
add("500019","500013","similar",  2)

add("500020","620006","crosssell",1)
add("500020","500016","similar",  2)

# ─────────────────────────────────────────────────────────────────────────────
# COOKIES  (400103)
# ─────────────────────────────────────────────────────────────────────────────
add("500021","600001","crosssell",1)   # Whole Milk
add("500021","600002","crosssell",2)   # 2% Milk
add("500021","500022","similar",  3)

add("500022","600008","crosssell",1)   # Chocolate Milk
add("500022","600001","crosssell",2)
add("500022","500021","similar",  3)
add("500022","500023","similar",  4)

add("500023","600001","crosssell",1)
add("500023","500022","similar",  2)

add("500024","630009","crosssell",1)   # Hazelnut Coffee Creamer
add("500024","630007","crosssell",2)   # Vanilla Cold Coffee
add("500024","500025","similar",  3)

add("500025","630007","crosssell",1)
add("500025","500024","similar",  2)

add("500026","600001","crosssell",1)
add("500026","730008","crosssell",2)   # Granola
add("500026","500021","similar",  3)

add("500027","600001","crosssell",1)
add("500027","500022","similar",  2)

add("500028","600001","crosssell",1)
add("500028","500021","similar",  2)

add("500029","630002","crosssell",1)   # Colombian Coffee
add("500029","500024","similar",  2)

add("500030","620006","crosssell",1)
add("500030","500020","similar",  2)

# ─────────────────────────────────────────────────────────────────────────────
# BREAD  (700101)
# ─────────────────────────────────────────────────────────────────────────────
add("710001","600016","crosssell",1)   # American Sliced Cheese
add("710001","600018","crosssell",2)   # Cream Cheese
add("710001","710002","similar",  3)

add("710002","600018","crosssell",1)
add("710002","600016","crosssell",2)
add("710002","710001","similar",  3)

add("710003","600015","crosssell",1)   # Swiss Sliced Cheese
add("710003","600018","crosssell",2)
add("710003","710004","similar",  3)

add("710004","600015","crosssell",1)
add("710004","600013","crosssell",2)   # Cheddar Chunk
add("710004","710003","similar",  3)

add("710005","600016","crosssell",1)
add("710005","710001","similar",  2)
add("710005","710002","similar",  3)
add("710005","710009","upsell",   4)   # Value Pack (larger)

add("710006","600018","crosssell",1)
add("710006","710003","similar",  2)

add("710007","600016","crosssell",1)
add("710007","710001","similar",  2)

add("710008","600015","crosssell",1)
add("710008","710003","similar",  2)

add("710009","600016","crosssell",1)
add("710009","710005","similar",  2)

add("710010","600015","crosssell",1)
add("710010","710003","similar",  2)
add("710010","710004","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM CAKES  (700102)
# ─────────────────────────────────────────────────────────────────────────────
add("720001","610001","crosssell",1)   # Cola for party
add("720001","200001","crosssell",2)   # Ice Cream
add("720001","720002","similar",  3)

add("720002","610001","crosssell",1)
add("720002","200002","crosssell",2)
add("720002","720001","similar",  3)

add("720003","610008","crosssell",1)
add("720003","200001","crosssell",2)
add("720003","720004","upsell",   3)   # Sheet Cake (larger)

add("720004","610008","crosssell",1)
add("720004","200008","crosssell",2)   # Party Size Ice Cream
add("720004","720003","similar",  3)

add("720005","610001","crosssell",1)
add("720005","200001","crosssell",2)
add("720005","720006","similar",  3)

add("720006","610008","crosssell",1)
add("720006","720001","similar",  2)

add("720007","200008","crosssell",1)
add("720007","610001","crosssell",2)
add("720007","720008","similar",  3)

add("720008","200001","crosssell",1)
add("720008","610004","crosssell",2)
add("720008","720007","similar",  3)

add("720009","200006","crosssell",1)
add("720009","630002","crosssell",2)
add("720009","720010","upsell",   3)   # Photo Cake

add("720010","200001","crosssell",1)
add("720010","610001","crosssell",2)
add("720010","720009","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# SOFT DRINKS  (600101)
# ─────────────────────────────────────────────────────────────────────────────
add("610001","500101","crosssell",1)
add("610001","500003","crosssell",2)
add("610001","610008","upsell",   3)   # MultiServe 2L
add("610001","610002","similar",  4)

add("610002","500109","crosssell",1)
add("610002","610001","similar",  2)
add("610002","610008","upsell",   3)

add("610003","500101","crosssell",1)
add("610003","500107","crosssell",2)
add("610003","610004","similar",  3)

add("610004","400009","crosssell",1)   # Kids Meal
add("610004","500101","crosssell",2)
add("610004","610003","similar",  3)

add("610005","500101","crosssell",1)
add("610005","610006","similar",  2)

add("610006","400005","crosssell",1)   # Pot Pie
add("610006","500101","crosssell",2)
add("610006","610001","similar",  3)

add("610007","500106","crosssell",1)   # Veggie Straws
add("610007","610010","similar",  2)

add("610008","400001","crosssell",1)   # Lasagna
add("610008","500003","crosssell",2)   # Pizza
add("610008","610001","similar",  3)

add("610009","400009","crosssell",1)
add("610009","610004","similar",  2)

add("610010","500106","crosssell",1)
add("610010","610007","similar",  2)

# ─────────────────────────────────────────────────────────────────────────────
# WATER  (600102)
# ─────────────────────────────────────────────────────────────────────────────
add("620001","500106","crosssell",1)   # Veggie Straws
add("620001","620003","upsell",   2)   # Sparkling upgrade
add("620001","620002","similar",  3)

add("620002","730001","crosssell",1)   # Cereal
add("620002","620001","similar",  2)

add("620003","500104","crosssell",1)   # Kettle Chips
add("620003","620004","similar",  2)

add("620004","500104","crosssell",1)
add("620004","620003","similar",  2)

add("620005","500016","crosssell",1)   # Better-For-You Crackers
add("620005","620002","similar",  2)

add("620006","500106","crosssell",1)
add("620006","620003","similar",  2)

add("620007","730008","crosssell",1)   # Granola
add("620007","620006","similar",  2)

add("620008","500104","crosssell",1)
add("620008","620004","similar",  2)

add("620009","500106","crosssell",1)
add("620009","620006","similar",  2)

add("620010","730001","crosssell",1)
add("620010","620001","similar",  2)

# ─────────────────────────────────────────────────────────────────────────────
# COFFEE  (600103)
# ─────────────────────────────────────────────────────────────────────────────
add("630001","630009","crosssell",1)   # Hazelnut Creamer
add("630001","500029","crosssell",2)   # Shortbread Cookies
add("630001","630002","upsell",   3)   # Premium Colombian

add("630002","630009","crosssell",1)
add("630002","500024","crosssell",2)   # Specialty Cookies
add("630002","630001","similar",  3)

add("630003","630009","crosssell",1)
add("630003","500024","crosssell",2)
add("630003","630004","similar",  3)

add("630004","630009","crosssell",1)
add("630004","500029","crosssell",2)
add("630004","630003","similar",  3)

add("630005","630009","crosssell",1)
add("630005","630002","similar",  2)
add("630005","630006","upsell",   3)   # Organic (premium)

add("630006","630009","crosssell",1)
add("630006","500029","crosssell",2)
add("630006","630005","similar",  3)

add("630007","500022","crosssell",1)   # Oreo
add("630007","630008","similar",  2)

add("630008","500021","crosssell",1)   # Chocolate Chip Cookies
add("630008","630007","similar",  2)

add("630009","630001","crosssell",1)
add("630009","630003","crosssell",2)
add("630009","630004","crosssell",3)

add("630010","630009","crosssell",1)
add("630010","630002","similar",  2)
add("630010","630005","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# CEREAL & BREAKFAST  (700200)
# ─────────────────────────────────────────────────────────────────────────────
add("730001","600001","crosssell",1)   # Whole Milk
add("730001","600002","crosssell",2)   # 2% Milk
add("730001","730006","similar",  3)   # Raisin Bran

add("730002","600008","crosssell",1)   # Chocolate Milk
add("730002","600001","crosssell",2)
add("730002","730001","similar",  3)

add("730003","600001","crosssell",1)
add("730003","730001","similar",  2)

add("730004","600001","crosssell",1)
add("730004","730002","similar",  2)

add("730005","600001","crosssell",1)
add("730005","730008","similar",  2)   # Granola

add("730006","600001","crosssell",1)
add("730006","730001","similar",  2)
add("730006","730009","similar",  3)

add("730007","600005","crosssell",1)   # Lactose-Free 2% Milk
add("730007","730010","similar",  2)

add("730008","700003","crosssell",1)   # Greek Yogurt Plain
add("730008","620007","crosssell",2)   # Coconut Water
add("730008","730005","similar",  3)

add("730009","600001","crosssell",1)
add("730009","730006","similar",  2)

add("730010","600001","crosssell",1)
add("730010","730007","similar",  2)

# ─────────────────────────────────────────────────────────────────────────────
# MILK  (400201)
# ─────────────────────────────────────────────────────────────────────────────
add("600001","730001","crosssell",1)   # Honey Crunch Cereal
add("600001","500021","crosssell",2)   # Chocolate Chip Cookies
add("600001","600002","similar",  3)

add("600002","730001","crosssell",1)
add("600002","500022","crosssell",2)   # Oreo
add("600002","600001","similar",  3)

add("600003","730003","crosssell",1)   # Corn Flakes
add("600003","600002","similar",  2)

add("600004","730001","crosssell",1)
add("600004","600005","similar",  2)

add("600005","730007","crosssell",1)   # Protein Cereal
add("600005","600004","similar",  2)

add("600006","730001","crosssell",1)
add("600006","600001","similar",  2)
add("600006","600007","similar",  3)

add("600007","730001","crosssell",1)
add("600007","600006","similar",  2)

add("600008","500022","crosssell",1)   # Oreo pairs with choc milk
add("600008","730002","crosssell",2)   # Chocolate Cereal
add("600008","600001","similar",  3)

add("600009","500021","crosssell",1)
add("600009","600001","similar",  2)

add("600010","730008","crosssell",1)   # Granola
add("600010","700003","crosssell",2)   # Greek Yogurt
add("600010","600003","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# YOGURT  (400202)
# ─────────────────────────────────────────────────────────────────────────────
add("700001","730008","crosssell",1)   # Granola
add("700001","620007","crosssell",2)   # Coconut Water
add("700001","700003","similar",  3)

add("700002","730008","crosssell",1)
add("700002","700001","similar",  2)

add("700003","730008","crosssell",1)
add("700003","620007","crosssell",2)
add("700003","700004","similar",  3)
add("700003","700010","upsell",   4)   # Siggi's (premium)

add("700004","730008","crosssell",1)
add("700004","700003","similar",  2)

add("700005","730008","crosssell",1)
add("700005","700006","similar",  2)

add("700006","700005","similar",  1)
add("700006","700003","similar",  2)

add("700007","600001","crosssell",1)
add("700007","700008","similar",  2)

add("700008","600001","crosssell",1)
add("700008","700007","similar",  2)

add("700009","500022","crosssell",1)
add("700009","700003","similar",  2)

add("700010","730008","crosssell",1)
add("700010","700003","similar",  2)

# ─────────────────────────────────────────────────────────────────────────────
# CHEESE  (400204 – 400210)
# ─────────────────────────────────────────────────────────────────────────────
# Mozzarella Shredded
add("600011","500003","crosssell",1)   # Pepperoni Pizza
add("600011","710001","crosssell",2)   # Bread
add("600011","600012","similar",  3)

# Cheddar Shredded
add("600012","710003","crosssell",1)   # Wheat Bread
add("600012","500012","crosssell",2)   # Ritz Crackers
add("600012","600011","similar",  3)

# Cheddar Chunk
add("600013","500013","crosssell",1)   # Wheat Grain Crackers
add("600013","600014","similar",  2)
add("600013","600012","similar",  3)

# Gouda Chunk
add("600014","500013","crosssell",1)
add("600014","620003","crosssell",2)   # Sparkling Water
add("600014","600013","similar",  3)

# Swiss Sliced
add("600015","710003","crosssell",1)
add("600015","500012","crosssell",2)
add("600015","600016","similar",  3)

# American Sliced
add("600016","710001","crosssell",1)
add("600016","710007","crosssell",2)
add("600016","600015","similar",  3)

# Cheese Cubes Snacking
add("600017","500101","crosssell",1)   # Chips
add("600017","620003","crosssell",2)
add("600017","600018","similar",  3)

# Cream Cheese Spread
add("600018","710001","crosssell",1)
add("600018","500012","crosssell",2)
add("600018","600017","similar",  3)

# Blue Cheese
add("600019","620004","crosssell",1)   # Soda Water
add("600019","500013","crosssell",2)
add("600019","600014","similar",  3)

# Vegan Cheddar
add("600020","600010","crosssell",1)   # Almond Milk
add("600020","500020","crosssell",2)   # Gluten-Free Crackers
add("600020","600019","similar",  3)

# ─────────────────────────────────────────────────────────────────────────────
# Write CSV
# ─────────────────────────────────────────────────────────────────────────────
with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["PRODUCT_ID", "RELATED_PRODUCT_ID", "RELATION_TYPE", "DISPLAY_ORDER"])
    w.writerows(rows)

print(f"✓  Meijer_crosssell.csv  →  {len(rows)} rows  →  {OUTPUT_CSV}")
crosssell = sum(1 for r in rows if r[2]=="crosssell")
upsell    = sum(1 for r in rows if r[2]=="upsell")
similar   = sum(1 for r in rows if r[2]=="similar")
print(f"   crosssell: {crosssell}  |  upsell: {upsell}  |  similar: {similar}")
