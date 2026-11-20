"""Generate original static documentation assets from literal fictional content."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    folder=ROOT/"assets";folder.mkdir(exist_ok=True)
    boxes=[(25,70,"1. PRODUCT IMPORT","Synthetic CSV + SHA-256"),(315,70,"2. VALIDATION","Atomic / Decimal / conflicts"),(605,70,"3. SEGMENT MATCH","Dedupe + exclusion evidence"),(895,70,"4. DRAFT GENERATION","Local rule, not an LLM"),(895,260,"5. HUMAN APPROVAL","Current revision + hash"),(605,260,"6. SIMULATION","Idempotent / no real mail"),(315,260,"7. ANALYTICS","Synthetic outcomes")]
    svg=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1190 410" role="img" aria-label="Seven-step simulated workflow"><rect width="1190" height="410" rx="22" fill="#f5f7fb"/><text x="28" y="38" font-family="sans-serif" font-size="20" font-weight="bold" fill="#243444">Enterprise Operations AI / transparent workflow</text><defs><marker id="arrow" markerWidth="7" markerHeight="7" refX="6" refY="3" orient="auto"><path d="M0 0L6 3L0 6" fill="#9b8bdc"/></marker></defs>']
    for x,y,title,detail in boxes:
        svg.append('<rect x="'+str(x)+'" y="'+str(y)+'" width="265" height="105" rx="13" fill="white" stroke="#ded8f1"/><text x="'+str(x+18)+'" y="'+str(y+38)+'" font-family="sans-serif" font-size="13" font-weight="bold" fill="#6858df">'+title+'</text><text x="'+str(x+18)+'" y="'+str(y+69)+'" font-family="sans-serif" font-size="11" fill="#72808f">'+detail+'</text>')
    for path in ("M290 120h20","M580 120h20","M870 120h20","M1025 180v70","M890 312h-20","M600 312h-20"):
        svg.append('<path d="'+path+'" fill="none" stroke="#9b8bdc" stroke-width="2" marker-end="url(#arrow)"/>')
    svg.append('<text x="28" y="390" font-family="sans-serif" font-size="12" fill="#72808f">Simulation is explicit. Every record is fictional. No external messages or model calls.</text></svg>')
    (folder/"workflow.svg").write_text("".join(svg),encoding="utf-8")
    lines=["Enterprise Operations AI","FICTIONAL EXAMPLE - NOT A REAL QUOTATION","Quotation: EXAMPLE-001 / version 1","Customer: Example Studio (fictional)","Product: EX-HALO-05 / Halo desk fixture","Quantity: 3    Unit price: USD 0.10","Subtotal: USD 0.30    Fictional tax: USD 0.02","Total: USD 0.32","Prepared for a local simulation only."]
    stream="BT /F1 18 Tf 50 780 Td "+" ".join(("("+line+") Tj 0 -35 Td") for line in lines)+" ET"
    objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",("<< /Length "+str(len(stream.encode()))+" >>\nstream\n"+stream+"\nendstream").encode()]
    raw=bytearray(b"%PDF-1.4\n");offsets=[0]
    for n,obj in enumerate(objects,1):
        offsets.append(len(raw));raw.extend((str(n)+" 0 obj\n").encode()+obj+b"\nendobj\n")
    index=len(raw);raw.extend(("xref\n0 "+str(len(offsets))+"\n0000000000 65535 f \n").encode())
    for offset in offsets[1:]: raw.extend(("%010d 00000 n \n"%offset).encode())
    raw.extend(("trailer\n<< /Size "+str(len(offsets))+" /Root 1 0 R >>\nstartxref\n"+str(index)+"\n%%EOF\n").encode())
    (folder/"example-quotation.pdf").write_bytes(raw)
if __name__=="__main__": main()
