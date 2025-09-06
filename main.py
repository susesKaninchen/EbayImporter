import csv
import os
import sys
import re

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'

def get_template_type(title, tags):
    """Determines the template type based on product title and tags."""
    title_lower = title.lower()
    tags_lower = tags.lower()

    accessory_keywords = ["beutel", "schale", "tasche", "box", "turm", "becher", "würfelbrett", "einlage", "tower", "tray", "bag"]
    if any(keyword in title_lower for keyword in accessory_keywords):
        return "wuerfelzubehoer"

    if "set" in title_lower or "set" in tags_lower:
        return "wuerfelsets"

    dice_keywords = ["w4", "w6", "w8", "w10", "w12", "w20", "w100", "d4", "d6", "d8", "d10", "d12", "d20", "d100"]
    if any(keyword in title_lower for keyword in dice_keywords):
        return "wuerfel"

    return "wuerfelsets"

def parse_html_description(html):
    """Parses the Body (HTML) to extract key details."""
    details = {
        'material': 'n.a.',
        'color': 'n.a.',
        'delivery_scope': 'n.a.',
        'short_description': ''
    }

    material_match = re.search(r"Material:\s*(.*?)(?:<br|</p>)", html, re.IGNORECASE)
    if material_match:
        details['material'] = material_match.group(1).strip()

    color_match = re.search(r"Farbe:\s*(.*?)(?:<br|</p>)", html, re.IGNORECASE)
    if color_match:
        details['color'] = color_match.group(1).strip()

    scope_match = re.search(r"Lieferumfang:\s*(.*?)(?:<br|</p>)", html, re.IGNORECASE)
    if scope_match:
        details['delivery_scope'] = scope_match.group(1).strip()

    text_content = re.sub('<[^<]+?>', ' ', html).strip()
    text_content = re.sub(r'\s+', ' ', text_content)
    sentences = text_content.split('.')
    if sentences:
        details['short_description'] = sentences[0].strip()

    return details

def main():
    """
    Main function to process the Shopify export and convert it to an eBay import file.
    """
    print("Starting script...")
    input_file = 'products_export_1.csv'
    output_file = 'ebay_import.csv'

    templates = {}
    for tpl_name in ["wuerfelsets", "wuerfel", "wuerfelzubehoer"]:
        try:
            with open(f'vorlage_{tpl_name}.html', 'r', encoding='utf-8') as f:
                templates[tpl_name] = f.read()
            print(f"Successfully loaded template: vorlage_{tpl_name}.html")
        except FileNotFoundError:
            print(f"FATAL: Template file vorlage_{tpl_name}.html not found.")
            return

    products = {}
    print(f"Reading from {input_file}...")
    try:
        with open(input_file, 'r', encoding='utf-8', newline='') as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                handle = row['Handle']
                if handle not in products:
                    products[handle] = {
                        'Title': row['Title'],
                        'Body (HTML)': row['Body (HTML)'],
                        'Vendor': row['Vendor'],
                        'Type': row['Type'],
                        'Tags': row['Tags'],
                        'Status': row['Status'],
                        'variants': [],
                        'images': set()
                    }
                
                products[handle]['variants'].append({
                    'Variant Price': row['Variant Price'],
                    'Variant SKU': row['Variant SKU'],
                    'Variant Inventory Qty': row['Variant Inventory Qty']
                })

                if row['Image Src']:
                    products[handle]['images'].add(row['Image Src'])
        print(f"Finished reading {input_file}. Found {len(products)} products.")

    except FileNotFoundError:
        print(f"Error: The file {input_file} was not found.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during file reading: {e}")
        return

    ebay_headers = [
        '*Action', '*Category', '*Title', '*Description', '*ConditionID',
        '*Format', '*Duration', '*StartPrice', '*Quantity', 'PicURL',
        'CustomLabel', 'Product:Brand', 'Location', 'Product:MPN', 'C:Marke',
        'PaymentProfileName', 'ShippingProfileName', 'ReturnProfileName'
    ]

    print(f"Writing to {output_file}...")
    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=ebay_headers)
        writer.writeheader()

        for handle, product_data in products.items():
            if product_data['Status'].lower() != 'active':
                continue

            print(f"Processing product: {product_data['Title']}")

            template_type = get_template_type(product_data['Title'], product_data['Tags'])
            template_str = templates[template_type]
            
            parsed_details = parse_html_description(product_data['Body (HTML)'])

            image_urls = '|'.join(product_data['images'])
            main_image = next(iter(product_data['images']), '')

            for variant in product_data['variants']:
                if not variant['Variant Inventory Qty'] or int(variant['Variant Inventory Qty']) <= 0:
                    continue

                description_line_1 = product_data['Body (HTML)'].split('</p>')[0].replace('<p>','')

                context = {
                    'title': product_data['Title'],
                    'price': variant['Variant Price'],
                    'image_url': main_image,
                    'short_description': parsed_details['short_description'],
                    'brand': product_data['Vendor'],
                    'detailed_title': product_data['Title'],
                    'description_line_1': description_line_1,
                    'material': parsed_details['material'],
                    'color': parsed_details['color'],
                    'delivery_scope': parsed_details['delivery_scope'],
                    'warning_html': '<p><strong>Warnung!</strong> Erstickungsgefahr durch verschluckbare Einzelteile! Nicht für Kinder unter 3 Jahren geeignet.</p>' if template_type != 'wuerfelzubehoer' else ''
                }

                final_description = template_str.format_map(SafeDict(context))

                ebay_row = {
                    '*Action': 'VerifyAdd',
                    '*Category': '7317',
                    '*Title': product_data['Title'],
                    '*Description': final_description,
                    '*ConditionID': '1000',
                    '*Format': 'FixedPrice',
                    '*Duration': 'GTC',
                    '*StartPrice': variant['Variant Price'],
                    '*Quantity': variant['Variant Inventory Qty'],
                    'PicURL': image_urls,
                    'CustomLabel': variant['Variant SKU'] or handle,
                    'Product:Brand': product_data['Vendor'],
                    'Location': 'Lübeck',
                    'Product:MPN': variant['Variant SKU'],
                    'C:Marke': product_data['Vendor'],
                    'PaymentProfileName': 'eBay Managed Payments (238923344012)',
                    'ShippingProfileName': 'Paket',
                    'ReturnProfileName': '1 month'
                }
                writer.writerow(ebay_row)

    print(f"\nProcessing complete. The eBay import file has been saved to {output_file}")

if __name__ == "__main__":
    main()