"""
Twinings UI Theme Migration
Replaces Bunnings teal/red theme with Twinings dark-brown/gold theme across all UI files.

Twinings Brand Colors:
  Dark Brown (header/footer/icons): #1A1008  (replaces teal #1B5252)
  Dark Brown 2:                     #0F0905  (replaces #133D3D)
  Mid Brown:                        #2D1F0E  (replaces #236060)
  Primary Gold CTA (Add to Cart):   #8B6520  (replaces red #D71920)
  Gold hover:                       #7A5018  (replaces #b5151b)
  Accent Gold:                      #C4973D  (replaces orange #F47920)
  Background:                       #FAF7F2  (cream, replaces #F2F2F2)
"""

import re

# ── color substitutions (order matters – most specific first) ─────────
COLOR_MAP = [
    # exact hex
    ('#133D3D', '#0F0905'),
    ('#236060', '#2D1F0E'),
    ('#1B5252', '#1A1008'),
    ('#D71920', '#8B6520'),
    ('#b5151b', '#7A5018'),
    ('#B5151B', '#7A5018'),
    ('#F47920', '#C4973D'),
    # rgba variants
    ('rgba(27, 82, 82,',  'rgba(26, 16, 8,'),
    ('rgba(27,82,82,',    'rgba(26,16,8,'),
    ('rgba(215, 25, 32,', 'rgba(139, 101, 32,'),
    ('rgba(215,25,32,',   'rgba(139,101,32,'),
    ('rgba(244, 121, 32,','rgba(196, 151, 61,'),
    ('rgba(244,121,32,',  'rgba(196,151,61,'),
    # Tailwind arbitrary color references in JS templates
    ('text-[#1B5252]',    'text-[#1A1008]'),
    ('hover:text-[#1B5252]', 'hover:text-[#1A1008]'),
    ('hover:border-[#1B5252]', 'hover:border-[#1A1008]'),
    # page background
    ('#F2F2F2', '#FAF7F2'),
    # gradient dot pattern
    ('rgba(27,82,82,0.06)', 'rgba(139,101,32,0.06)'),
    ('rgba(27, 82, 82, 0.06)', 'rgba(139,101,32,0.06)'),
]

# ── text / branding substitutions ─────────────────────────────────────
TEXT_MAP = [
    # page title
    ('Bunnings AI Shopping Assistant', 'Twinings AI Shopping Assistant'),
    # chat area input placeholder
    ('Ask me anything about Bunnings products...', 'Ask me about Twinings teas & gifts...'),
    # footer brand text  
    ('AI-powered Bunnings assistant.', 'AI-powered Twinings tea shopping assistant.'),
    ('Experience the future of hardware & home shopping with our AI-powered Bunnings assistant.', 
     'Experience the future of tea shopping with our AI-powered Twinings assistant.'),
    ('&copy; 2026 Bunnings AI Shopping Assistant. Powered by Capgemini Agentic AI.',
     '&copy; 2026 Twinings AI Shopping Assistant. Powered by Capgemini Agentic AI.'),
    # footer brand logo text
    ('<span class="font-black text-xl tracking-tight" style="color:#8B6520;">BUNNINGS</span>',
     '<span class="font-black text-xl tracking-tight" style="color:#C4973D;">TWININGS</span>'),
    # footer description  
    ('Explore Bunnings product range', 'Explore Twinings tea range'),
    # order card
    ('Bunnings Warehouse', 'Twinings Tea Shop'),
    # product detail page
    ('.product-price {\n            font-size: 1.5rem;\n            color: #e60023;',
     '.product-price {\n            font-size: 1.5rem;\n            color: #8B6520;'),
    ('back-link {\n            display: inline-block;\n            margin-top: 30px;\n            padding: 10px 20px;\n            background: #4CAF50;',
     'back-link {\n            display: inline-block;\n            margin-top: 30px;\n            padding: 10px 20px;\n            background: #8B6520;'),
    # CSS comment
    ('/* AI Shopping Assistant - Bunnings Warehouse Theme */',
     '/* AI Shopping Assistant - Twinings Tea Theme */'),
    ('/* Bunnings Color Palette */', '/* Twinings Color Palette */'),
    ('--bunnings-teal:', '--twinings-dark:'),
    ('--bunnings-teal-dark:', '--twinings-dark-deep:'),
    ('--bunnings-teal-mid:', '--twinings-dark-mid:'),
    ('--bunnings-red:', '--twinings-gold:'),
    ('--bunnings-red-hover:', '--twinings-gold-hover:'),
    ('--bunnings-orange:', '--twinings-accent:'),
    ('--bunnings-light-bg:', '--twinings-light-bg:'),
    ('--bunnings-card-bg:', '--twinings-card-bg:'),
    ('--bunnings-text:', '--twinings-text:'),
    ('--bunnings-text-muted:', '--twinings-text-muted:'),
    ('--bunnings-border:', '--twinings-border:'),
    ('/* Chat Bubbles - Bunnings Theme */', '/* Chat Bubbles - Twinings Theme */'),
    ('/* Custom scrollbar styles - Bunnings Teal Theme */', '/* Custom scrollbar styles - Twinings Gold Theme */'),
    # brainGlow animation - red color removal
    ('color: #D71920;\n    text-shadow: 0 0 10px rgba(215, 25, 32, 0.6);',
     'color: #C4973D;\n    text-shadow: 0 0 10px rgba(196, 151, 61, 0.6);'),
    # renderBunningsOrderCard → renderTwiningsOrderCard
    ('renderBunningsOrderCard', 'renderTwiningsOrderCard'),
    ('function renderBunningsOrderCard', 'function renderTwiningsOrderCard'),
]

# ── logo block replacement ─────────────────────────────────────────────
OLD_LOGO = '''<div class="flex flex-col items-start">
              <div class="flex items-center space-x-2">
                <div>
                  <img src="/static/assets/logoBunning.jpg" alt="Bunnings Warehouse" style="height:70px; width:auto; object-fit:contain; border-radius:6px;">
                </div>
              </div>
              <p class="text-white/70 text-xs mt-1 tracking-wide">AI POWERED SHOPPING ASSISTANT</p>
            </div>'''

NEW_LOGO = '''<div class="flex flex-col items-start">
              <div class="flex items-center space-x-2">
                <div class="flex items-center px-4 py-2 rounded-xl" style="background:#FAF7F2;">
                  <span class="font-black text-2xl tracking-widest" style="color:#1A1008; letter-spacing:0.12em;">TWININGS</span>
                </div>
              </div>
              <p class="text-white/70 text-xs mt-1 tracking-wide">AI POWERED SHOPPING ASSISTANT</p>
            </div>'''

# ── category section replacement ──────────────────────────────────────
OLD_CATEGORIES = '''<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="power tools" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me power tools\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #1B5252;">
            <i class="fas fa-tools text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Power Tools</h3>
          <p class="text-xs text-gray-500">Drills, drivers & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="garden" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me indoor plants\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #2E7D32;">
            <i class="fas fa-leaf text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Garden & Plants</h3>
          <p class="text-xs text-gray-500">Indoor & outdoor plants</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="lighting" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me lighting\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #F47920;">
            <i class="fas fa-lightbulb text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Lighting</h3>
          <p class="text-xs text-gray-500">Pendant lights & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="phones" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me mobile phones\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #D71920;">
            <i class="fas fa-mobile-alt text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Mobile Phones</h3>
          <p class="text-xs text-gray-500">Phones & accessories</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="kitchen" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me kitchen appliances\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #1B5252;">
            <i class="fas fa-blender text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Kitchen</h3>
          <p class="text-xs text-gray-500">Kettles, toasters & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="cameras" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me cameras\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #1B5252;">
            <i class="fas fa-camera text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Cameras</h3>
          <p class="text-xs text-gray-500">DSLR & accessories</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="door hardware" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me door hardware\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #5D4037;">
            <i class="fas fa-door-open text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Door Hardware</h3>
          <p class="text-xs text-gray-500">Handles, locks & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="audio" style="border-color:#DDDDDD;" onclick="document.getElementById(\'query\').value=\'show me headphones and speakers\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #1565C0;">
            <i class="fas fa-headphones text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Audio & TVs</h3>
          <p class="text-xs text-gray-500">Headphones, speakers & TVs</p>
        </div>
      </div>'''

NEW_CATEGORIES = '''<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="black tea" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me black tea\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #1A1008;">
            <i class="fas fa-mug-hot text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Black Tea</h3>
          <p class="text-xs text-gray-500">English Breakfast & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="green tea" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me green tea\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #2E7D32;">
            <i class="fas fa-leaf text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Green Tea</h3>
          <p class="text-xs text-gray-500">Jasmine, Sencha & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="herbal" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me herbal tea\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #5D8D3C;">
            <i class="fas fa-seedling text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Herbal & Fruit</h3>
          <p class="text-xs text-gray-500">Chamomile, Peppermint & more</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="superblends" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me superblends\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #8B6520;">
            <i class="fas fa-star text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Superblends</h3>
          <p class="text-xs text-gray-500">Wellness tea blends</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="sparkling tea" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me sparkling tea\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #4A90D9;">
            <i class="fas fa-wine-glass-alt text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Sparkling Tea</h3>
          <p class="text-xs text-gray-500">Premium sparkling drinks</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="luxury gifts" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me luxury gift sets\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #9B2335;">
            <i class="fas fa-gift text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Luxury Gifts</h3>
          <p class="text-xs text-gray-500">Premium curated sets</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="gift boxes" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me gift boxes\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #C4973D;">
            <i class="fas fa-box-open text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Gift Boxes</h3>
          <p class="text-xs text-gray-500">Hampers & assortments</p>
        </div>
        
        <div class="rounded-xl p-5 text-center hover:shadow-lg transition-all duration-200 cursor-pointer group bg-white border" data-category="teaware" style="border-color:#E8DFCF;" onclick="document.getElementById(\'query\').value=\'show me teaware\'; submitQuery();">
          <div class="w-14 h-14 rounded-xl flex items-center justify-center mx-auto mb-3 group-hover:scale-110 transition-transform duration-200" style="background: #5D4037;">
            <i class="fas fa-mug-hot text-white text-2xl"></i>
          </div>
          <h3 class="font-semibold text-gray-800 mb-0.5">Teaware</h3>
          <p class="text-xs text-gray-500">Teapots, mugs & infusers</p>
        </div>
      </div>'''

# ── category section heading ───────────────────────────────────────────
OLD_CAT_HEADING = '''        <h2 class="text-3xl font-bold text-gray-800 font-poppins">Shop by Category</h2>
        <p class="text-gray-600 mt-2">Explore Bunnings product range</p>'''
NEW_CAT_HEADING = '''        <h2 class="text-3xl font-bold text-gray-800 font-poppins">Shop by Category</h2>
        <p class="text-gray-600 mt-2">Explore the Twinings tea range</p>'''

# ── footer border top ──────────────────────────────────────────────────
OLD_FOOTER = 'style="background: #1B5252; border-top: 3px solid #D71920;">'
NEW_FOOTER = 'style="background: #1A1008; border-top: 3px solid #C4973D;">'

# ── welcome message – body text ────────────────────────────────────────
OLD_WELCOME = '''<p class="font-medium text-gray-800">Hello! I'm your AI shopping assistant powered by Capgemini.</p>
                  <p class="text-gray-600 text-sm mt-1">How can I help you find the perfect products today?</p>'''
NEW_WELCOME = '''<p class="font-medium text-gray-800">Hello! I'm your Twinings AI shopping assistant powered by Capgemini.</p>
                  <p class="text-gray-600 text-sm mt-1">How can I help you find the perfect tea or gift today?</p>'''

# ── body background ────────────────────────────────────────────────────
OLD_BODY = 'style="background-color: #F2F2F2;">'
NEW_BODY = 'style="background-color: #FAF7F2;">'

# ── crosssell bg color in app.js ──────────────────────────────────────
OLD_CROSSSELL = 'crosssell: { label: "You may need",  bg: "#D71920" },'
NEW_CROSSSELL  = 'crosssell: { label: "You may need",  bg: "#8B6520" },'

# ──────────────────────────────────────────────────────────────────────
def process_file(path, extra_replacements=None):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # colour map
    for old, new in COLOR_MAP:
        content = content.replace(old, new)
    
    # text map
    for old, new in TEXT_MAP:
        content = content.replace(old, new)
    
    # extra per-file replacements
    if extra_replacements:
        for old, new in extra_replacements:
            if old in content:
                content = content.replace(old, new)
                print(f"  ✅ Applied: {old[:60]}...")
            else:
                print(f"  ⚠️  Not found: {old[:60]}...")
    
    changed = content != original
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    return changed

# ──────────────────────────────────────────────────────────────────────
print("=" * 60)
print("Twinings Theme Migration")
print("=" * 60)

# CSS
print("\n[1/4] styles.css")
process_file(r'c:\Agentic Ai\TwningDemo\static\css\styles.css')
print("  ✅ Done")

# index.html
print("\n[2/4] index.html")
process_file(
    r'c:\Agentic Ai\TwningDemo\templates\index.html',
    extra_replacements=[
        (OLD_LOGO, NEW_LOGO),
        (OLD_CATEGORIES, NEW_CATEGORIES),
        (OLD_CAT_HEADING, NEW_CAT_HEADING),
        (OLD_FOOTER, NEW_FOOTER),
        (OLD_WELCOME, NEW_WELCOME),
        (OLD_BODY, NEW_BODY),
    ]
)
print("  ✅ Done")

# product_detail.html
print("\n[3/4] product_detail.html")
process_file(r'c:\Agentic Ai\TwningDemo\templates\product_detail.html')
print("  ✅ Done")

# app.js
print("\n[4/4] app.js")
process_file(
    r'c:\Agentic Ai\TwningDemo\static\js\app.js',
    extra_replacements=[
        (OLD_CROSSSELL, NEW_CROSSSELL),
    ]
)
print("  ✅ Done")

# ── verify no old red / teal left in UI files ─────────────────────────
print("\n--- Verification ---")
ui_files = [
    r'c:\Agentic Ai\TwningDemo\static\css\styles.css',
    r'c:\Agentic Ai\TwningDemo\templates\index.html',
    r'c:\Agentic Ai\TwningDemo\templates\product_detail.html',
    r'c:\Agentic Ai\TwningDemo\static\js\app.js',
]
CHECK_COLORS = ['#D71920', '#b5151b', '#1B5252', '#133D3D', '#236060', 'logoBunning', 'Bunnings Warehouse']
for fpath in ui_files:
    fname = fpath.split('\\')[-1]
    with open(fpath, encoding='utf-8') as f:
        lines = f.readlines()
    hits = [(i+1, l.strip()[:100]) for i, l in enumerate(lines)
            if any(c in l for c in CHECK_COLORS)]
    if hits:
        print(f"  ⚠️  {fname}: {len(hits)} remaining refs:")
        for ln, text in hits[:5]:
            print(f"      Line {ln}: {text}")
    else:
        print(f"  ✅ {fname}: CLEAN")

print("\n✅ Theme migration complete!")
