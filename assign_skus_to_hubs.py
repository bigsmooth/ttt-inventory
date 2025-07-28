import sqlite3
from tabulate import tabulate

conn = sqlite3.connect("barcodes.db")
cursor = conn.cursor()

# Step 1: Ensure table exists
cursor.execute("""
CREATE TABLE IF NOT EXISTS hub_skus (
    hub_id INTEGER,
    sku TEXT,
    PRIMARY KEY (hub_id, sku),
    FOREIGN KEY (hub_id) REFERENCES hubs(id),
    FOREIGN KEY (sku) REFERENCES products(sku)
)
""")

# Step 2: SKU assignments per hub
assignments = [
    # Hub 1
    (1, 'TTT-SOL-BLASOL-PLUS'),
    (1, 'TTT-STR-BLAWHISTR-PLUS'),
    (1, 'TTT-STR-ALLAMESTR-PLUS'),
    (1, 'TTT-STR-CARBLUWHISTR-PLUS'),
    (1, 'TTT-STR-BLAHOTPINSTR-PLUS'),
    (1, 'TTT-STR-NAVSILSTR-PLUS'),

    # Hub 2
    (2, 'TTT-SOL-BLASOL-PLUS'),
    (2, 'TTT-STR-BLAWHISTR-PLUS'),
    (2, 'TTT-STR-BLAGRESTR-PLUS'),
    (2, 'TTT-STR-BLAPURSTR-PLUS'),
    (2, 'TTT-STR-BLAYELSTR-PLUS'),
    (2, 'TTT-STR-BLOBRESTR-PLUS'),
    (2, 'TTT-STR-ELEBLUWHISTR-PLUS'),
    (2, 'TTT-STR-ORABLASTR-PLUS'),
    (2, 'TTT-STR-WHTGRN'),
    (2, 'TTT-STR-PATS-PLUS'),
    (2, 'TTT-SOL-PLUM-PLUS'),
    (2, 'TTT-STR-SNOAN-PLUS'),
    (2, 'TTT-STR-CRANFR-PLUS'),
    (2, 'TTT-STR-WITVIBSTR-PLUS'),

    # Hub 3
    (3, 'TTT-SOL-BLASOL-PLUS'),
    (3, 'TTT-STR-BLAWHISTR-PLUS'),
    (3, 'TTT-STR-BLAGRYSTR-PLUS'),
    (3, 'TTT-STR-BLAGRESTR-PLUS'),
    (3, 'TTT-SOL-HEASOC-PLUS'),
    (3, 'TTT-STR-BLAREDSTR-PLUS'),
    (3, 'TTT-STR-RAISTR-PLUS'),
    (3, 'TTT-STR-SMOGREBLASTR-PLUS'),
    (3, 'TTT-STR-PCHSTR-PLUS'),
    (3, 'TTT-STR-SEA-PLUS'),
    (3, 'TTT-THN-BLASOLID-PLUS'),
    (3, 'TTT-THN-BLAWWHITESTRIPES-PLUS'),

    # Retail Store (ID 99)
    (99, 'TTT-SOL-BLASOL-PLUS'),
    (99, 'TTT-SOL-BUB-PLUS'),
    (99, 'TTT-SOL-TANSOL-PLUS'),
    (99, 'TTT-SOL-HOTPINSOL-PLUS'),
    (99, 'TTT-SOL-BROSOL-PLUS'),
    (99, 'TTT-SOL-DARCHESOL-PLUS'),
    (99, 'TTT-SOL-WINWHISOL-PLUS'),
    (99, 'TTT-SOL-CORALSOL-PLUS'),
    (99, 'TTT-SOL-NAVSOL-PLUS'),
    (99, 'TTT-SOL-ELEBLUSOL-PLUS'),
    (99, 'TTT-SOL-CELGRE-PLUS'),
    (99, 'TTT-SOL-CHESOL-PLUS'),
    (99, 'TTT-SOL-SMOGRESOL-PLUS'),
    (99, 'TTT-SOL-CHAGRE-PLUS'),
    (99, 'TTT-SOL-LOVLIL-PLUS'),
    (99, 'TTT-SOL-CARBLUSOL-PLUS'),
    (99, 'TTT-SOL-JUIPUR-PLUS'),
    (99, 'TTT-STR-GRNREDSTR-PLUS'),
    (99, 'TTT-STR-WINGRESTR-PLUS'),
    (99, 'TTT-STR-MIDFROSTR-PLUS'),
    (99, 'TTT-STR-WITVIBSTR-PLUS'),
    (99, 'TTT-STR-LTPURWHISTR-PLUS'),
    (99, 'TTT-STR-PEPSRI-PLUS'),
    (99, 'TTT-STR-REDBLKSTR-PLUS'),
    (99, 'TTT-STR-GOTCHISTR-PLUS'),
    (99, 'TTT-STR-SUGRUSSTR-PLUS'),
    (99, 'TTT-STR-EMEONYSTR-PLUS'),
    (99, 'TTT-STR-PUMSPISTR-PLUS'),
    (99, 'TTT-STR-PNKWHISTR-PLUS'),
    (99, 'TTT-STR-ALLAMESTR-PLUS'),
    (99, 'TTT-STR-CANCANSTR-PLUS'),
    (99, 'TTT-STR-BLOBRESTR-PLUS'),
    (99, 'TTT-STR-WHIICEBLUSTR-PLUS'),
    (99, 'TTT-STR-CHRFESSTR-PLUS'),
    (99, 'TTT-STR-WHIBLASTR-PLUS'),
    (99, 'TTT-STR-NAVWHISTR-PLUS'),
    (99, 'TTT-STR-ELEBLUWHISTR-PLUS'),
    (99, 'TTT-STR-CELGREWHISTR-PLUS'),
    (99, 'TTT-STR-TWLPOP-PLUS'),
    (99, 'TTT-STR-BLAMULSTR-PLUS'),
    (99, 'TTT-STR-BLAHOTPINSTR-PLUS'),
    (99, 'TTT-STR-BLAYELSTR-PLUS'),
    (99, 'TTT-STR-BHMSTR-PLUS'),
    (99, 'TTT-SOL-SOLGLO-PLUS'),
    (99, 'TTT-STR-NAVSILSTR-PLUS'),
    (99, 'TTT-STR-CHEWHISTR-PLUS'),
    (99, 'TTT-STR-WHEWHISTR-PLUS'),
    (99, 'TTT-STR-BROWHISTR-PLUS'),
    (99, 'TTT-STR-WHTWGRTRSTR-PLUS'),
    (99, 'TTT-STR-CORWHTSTR-PLUS'),
    (99, 'TTT-STR-IMPPURWHISTR-PLUS'),
    (99, 'TTT-STR-CARBLUWHISTR-PLUS'),
    (99, 'TTT-STR-SMOGREWHISTR-PLUS'),
    (99, 'TTT-STR-BLAWHISTR-PLUS'),
    (99, 'TTT-STR-BUBGUMWHISTR-PLUS'),
    (99, 'TTT-STR-DARCHEWHISTR-PLUS'),
    (99, 'TTT-STR-HOTPINWHISTR-PLUS'),
    (99, 'TTT-STR-ORABLASTR-PLUS'),
    (99, 'TTT-STR-BLAORGSTR-PLUS'),
    (99, 'TTT-STR-BLAREDSTR-PLUS'),
    (99, 'TTT-STR-SMOGREBLASTR-PLUS'),
    (99, 'TTT-SOL-ROYBLU-PLUS'),
    (99, 'TTT-STR-BLAGRYSTR-PLUS'),
    (99, 'TTT-STR-BLAPURSTR-PLUS'),
    (99, 'TTT-STR-RAISTR-PLUS'),
    (99, 'TTT-STR-WHIGRESTR-PLUS'),
    (99, 'TTT-STR-BLAGRESTR-PLUS'),
    (99, 'TTT-SOL-HEASOC-PLUS'),
    (99, 'TTT-SOL-SHASOC-PLUS'),
    (99, 'TTT-SOL-PLUM-PLUS'),
    (99, 'TTT-SOL-PUMSOL-PLUS'),
    (99, 'TTT-STR-PCHSTR-PLUS'),
    (99, 'TTT-STR-CRANFRSTR-PLUS'),
    (99, 'TTT-STR-SNOWAN-PLUS'),
    (99, 'TTT-STR-PATS-PLUS'),
    (99, 'TTT-STR-SEA-PLUS'),
    (99, 'TTT-THN-BLASOLID-PLUS'),
    (99, 'TTT-THN-WHISOLID-PLUS'),
    (99, 'TTT-THN-BLAWWHITESTRIPES-PLUS'),
    (99, 'TTT-THN-YEL-PLUS'),
    (99, 'TTT-THN-BLAWREDSTRIPES-PLUS'),
    (99, 'TTT-THN-BLAWPNKSTRIPES-PLUS'),
    (99, 'TTT-THN-HOTPINWHISTRIPES-PLUS'),
    (99, 'TTT-SOL-BLKSOL-SHORT'),
    (99, 'TTT-SOL-WHTSOL-SHORT'),
    (99, 'TTT-STR-BWWHT-SHORT')
]

# Step 3: Insert all
cursor.executemany("INSERT OR IGNORE INTO hub_skus (hub_id, sku) VALUES (?, ?)", assignments)
conn.commit()

# Step 4: Verify all hub SKUs
print("\n🧾 Verifying all assigned SKUs per hub:\n")
cursor.execute("SELECT id, name FROM hubs ORDER BY id")
hubs = cursor.fetchall()

for hub_id, hub_name in hubs:
    cursor.execute("SELECT sku FROM hub_skus WHERE hub_id = ? ORDER BY sku", (hub_id,))
    skus = cursor.fetchall()
    print(f"🏬 {hub_name} (ID: {hub_id}) — {len(skus)} SKUs")
    if skus:
        print(tabulate(skus, headers=["SKU"], tablefmt="grid"))
    else:
        print("❌ No SKUs assigned.")
    print("\n" + "-" * 60 + "\n")

conn.close()
print("✅ All hub SKUs assigned and verified successfully.")
