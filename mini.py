import fitz  # PyMuPDF
import re    # For regex to handle whitespace variations
import io
from PIL import Image
import numpy as np  # For better pixel handling with tolerance

def replace_black_to_gray(input_pdf, output_pdf, process_images=True, tolerance=30):
    doc = fitz.open(input_pdf)
    print(f"Processing pages 22-25 (indices 21-24) out of {len(doc)} total pages...")
    print(f"Image processing: {'Enabled' if process_images else 'Disabled'} (tolerance for near-black: {tolerance})")

    # Regex patterns to match black colors with optional whitespace (common in PDF streams)
    black_patterns = [
        # RGB fill (rg): 0 0 0 rg
        (r'\b0\s+0\s+0\s+rg\b', '0.5 0.5 0.5 rg'),
        # RGB stroke (RG): 0 0 0 RG
        (r'\b0\s+0\s+0\s+RG\b', '0.5 0.5 0.5 RG'),
        # Gray fill (g): 0 g
        (r'\b0\s+g\b', '0.5 g'),
        # Gray stroke (G): 0 G
        (r'\b0\s+G\b', '0.5 G'),
        # CMYK fill (k): 0 0 0 1 k (rich black to 50% tint)
        (r'\b0\s+0\s+0\s+1\s+k\b', '0 0 0 0.5 k'),
        # CMYK stroke (K): 0 0 0 1 K
        (r'\b0\s+0\s+0\s+1\s+K\b', '0 0 0 0.5 K'),
        # Non-stroking color (cs): 0 0 0 scn (for named/spot, but basic black)
        (r'\b0\s+0\s+0\s+scn\b', '0.5 0.5 0.5 scn'),
        # Stroking color (CS): 0 0 0 SCN
        (r'\b0\s+0\s+0\s+SCN\b', '0.5 0.5 0.5 SCN'),
    ]

    for page_num in range(21, 25):  # Pages 22-25 (0-indexed: 21 to 24)
        page = doc[page_num]
        xref_list = page.get_contents()

        for xref in xref_list:
            # Extract the raw stream as text (ignore binary parts if any)
            try:
                raw_bytes = doc.xref_stream(xref)
                stream = raw_bytes.decode("latin1")  # Better for PDF streams: latin1 handles all bytes without loss
            except:
                stream = ""  # Skip if unreadable

            if not stream:
                print(f"Warning: Empty stream for xref {xref} on page {page_num + 1}")
                continue

            # Debug: For first test page (22), print counts before/after
            if page_num == 21:
                before_count = len(re.findall(r'0\s+0\s+0\s+rg', stream, re.IGNORECASE))
                print(f"Page 22 before: Found {before_count} instances of '0 0 0 rg'")

            # Apply regex replaces for each pattern
            original_stream = stream
            for pattern, replacement in black_patterns:
                stream = re.sub(pattern, replacement, stream, flags=re.IGNORECASE)

            # Debug: Check if changes happened
            if page_num == 21:
                after_count = len(re.findall(r'0\s+0\s+0\s+rg', stream, re.IGNORECASE))
                print(f"Page 22 after: Found {after_count} instances of '0 0 0 rg' (should be 0 if replaced)")
                if before_count > 0 and after_count == before_count:
                    print("No replacements happened—check stream encoding!")
                    # Quick peek at first match
                    match = re.search(r'0\s+0\s+0\s+rg', original_stream, re.IGNORECASE)
                    if match:
                        print(f"Sample match: '{match.group(0)}'")

            # If no change detected and it's the first test page, try naive string replace as fallback
            if page_num == 21 and after_count > 0:
                print("Trying naive string replace fallback...")
                stream = stream.replace("0 0 0 rg", "0.5 0.5 0.5 rg")

            # Update the stream (PyMuPDF handles length updates; use original bytes for non-text parts if needed, but here it's text)
            updated_bytes = stream.encode("latin1")  # Re-encode with latin1 to preserve any non-UTF8
            doc.update_stream(xref, updated_bytes)

        # New: Process images on this page (only if enabled)
        if process_images:
            image_list = page.get_images()
            print(f"Page {page_num + 1}: Found {len(image_list)} images to process.")
            for img_index, img in enumerate(image_list):
                xref_img = img[0]
                base_image = doc.extract_image(xref_img)
                image_bytes = base_image["image"]
                img_pil = Image.open(io.BytesIO(image_bytes))
               
                # Convert to RGB if not (avoid RGBA alpha issues in PDFs)
                if img_pil.mode != 'RGB':
                    img_pil = img_pil.convert('RGB')
               
                # Use numpy for efficient near-black detection/replacement
                img_array = np.array(img_pil)
                # Detect near-black: where all channels < tolerance
                mask = np.all(img_array < tolerance, axis=2)
                # Set to gray (128,128,128)
                img_array[mask] = [128, 128, 128]
                img_pil = Image.fromarray(img_array)
               
                # Re-encode as JPEG (better compatibility for PDF embeds than PNG; reduces artifacts)
                output = io.BytesIO()
                img_pil.save(output, format='JPEG', quality=95, optimize=True)
                jpeg_data = output.getvalue()
               
                # Update stream with JPEG data (PyMuPDF auto-detects /DCTDecode for JPEG bytes)
                doc.update_stream(xref_img, jpeg_data, compress=False)  # No extra deflation for JPEG
                print(f"  - Image {img_index + 1} processed (now JPEG; auto-filtered).")

        print(f"Page {page_num + 1} done.")

    doc.save(output_pdf, garbage=4, deflate=True)  # Clean up and compress
    doc.close()
    print(f"Mini-test output saved: {output_pdf} (only pages 22-25 processed; others unchanged)")
    print("Test: Open the output and check pages 22-25 for gray text/blocks—text should still be selectable.")
    print("If still corrupted, re-run with process_images=False to isolate vector-only changes.")

# Usage: replace with your repaired file (processes only pages 22-25)
# Set process_images=False to skip images and test vectors alone
replace_black_to_gray("/home/atharv/repaired.pdf", "gray_test_pages22-25_v5.pdf", process_images=False, tolerance=30)
