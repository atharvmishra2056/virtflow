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
            for pattern, replacement in black_patterns:
                stream = re.sub(pattern, replacement, stream, flags=re.IGNORECASE)

            # Debug: Check if changes happened
            if page_num == 21:
                after_count = len(re.findall(r'0\s+0\s+0\s+rg', stream, re.IGNORECASE))
                print(f"Page 22 after: Found {after_count} instances of '0 0 0 rg' (should be 0 if replaced)")

            # Update the stream
            updated_bytes = stream.encode("latin1")
            doc.update_stream(xref, updated_bytes)

        # Process images on this page (only if enabled) - Proper replacement to avoid corruption
        if process_images:
            image_list = page.get_images()
            print(f"Page {page_num + 1}: Found {len(image_list)} images to process.")
            for img_index, img in enumerate(image_list):
                xref_img = img[0]
                smask_xref = img[7] if len(img) > 7 else 0  # Soft mask xref if present
                print(f"  - Processing image {img_index + 1} (xref: {xref_img}, smask: {smask_xref})")

                # Extract and process the image with PIL + NumPy
                base_image = doc.extract_image(xref_img)
                image_bytes = base_image["image"]
                img_pil = Image.open(io.BytesIO(image_bytes))
                
                if img_pil.mode != 'RGB':
                    img_pil = img_pil.convert('RGB')
                
                # Near-black to gray
                img_array = np.array(img_pil)
                mask = np.all(img_array < tolerance, axis=2)
                img_array[mask] = [128, 128, 128]
                img_pil = Image.fromarray(img_array)
                
                # Create PNG bytes for Pixmap
                output = io.BytesIO()
                img_pil.save(output, format='PNG')
                png_data = output.getvalue()
                
                # Create new Pixmap from PNG bytes
                processed_pix = fitz.Pixmap(doc, png_data)
                
                # Handle mask if present (simple alpha blend; extend if needed)
                if smask_xref > 0:
                    mask_img = doc.extract_image(smask_xref)["image"]
                    mask_pix = fitz.Pixmap(doc, mask_img)
                    processed_pix = fitz.Pixmap(processed_pix, mask_pix)
                    mask_pix = None  # Free
                
                # Insert new image at page rect (assuming full-page background; adjust rect if partial)
                insert_rect = page.rect  # Or use page.get_image_rects(xref_img)[0] for precise
                new_xref = page.insert_image(insert_rect, pixmap=processed_pix)
                
                # Copy new xref over old
                doc.xref_copy(new_xref, xref_img)
                
                # Blank the new contents stream created by insert_image
                contents = page.get_contents()
                if contents:
                    last_c = contents[-1]
                    doc.update_stream(last_c, b" ")
                
                print(f"    Replaced successfully (new xref: {new_xref})")
                processed_pix = None  # Free memory

        print(f"Page {page_num + 1} done.")

    # Clear cache to force refresh and avoid rendering glitches
    fitz.Tools().store_shrink(100)
    
    doc.save(output_pdf, garbage=4, deflate=True)  # Clean up and compress
    doc.close()
    print(f"Mini-test output saved: {output_pdf} (only pages 22-25 processed; others unchanged)")
    print("Test: Open the output and check pages 22-25—gray text/blocks without overlay corruption; text selectable.")

# Usage: processes only pages 22-25 with images fixed properly
replace_black_to_gray("/home/atharv/repaired.pdf", "gray_test_pages22-25_final.pdf", process_images=True, tolerance=30)
