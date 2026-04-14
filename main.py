import csv
import os
import sys
import re
import json

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'

def truncate_title(title: str, max_len: int = 80) -> str:
    """Truncate eBay title to <= max_len characters, prefer word boundary."""
    t = (title or '').strip()
    if len(t) <= max_len:
        return t
    cut = t[:max_len]
    # try to cut at last space to avoid mid-word breaks
    sp = cut.rfind(' ')
    if sp >= max_len * 0.5:  # only use space if reasonably within the cut
        return cut[:sp].rstrip()
    return cut.rstrip()

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

    return "spiel"

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

def load_category_mapping(path='category_mapping.json'):
    """Load category mapping from JSON. Provides sane defaults if missing/invalid."""
    default_mapping = {
        "by_template": {
            "wuerfelsets": "7317",
            "wuerfel": "7317",
            "wuerfelzubehoer": "7317",
            "spiel": "7317"
        },
        "by_tag_contains": {},
        "by_title_contains": {},
        "by_type_equals": {},
        "default": "7317"
    }
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Merge with defaults to ensure keys exist
            for k, v in default_mapping.items():
                if k not in data:
                    data[k] = v
            print(f"Loaded category mapping from {path}")
            return data
    except FileNotFoundError:
        print(f"Category mapping file {path} not found. Using defaults.")
        return default_mapping
    except Exception as e:
        print(f"Warning: Failed to load category mapping: {e}. Using defaults.")
        return default_mapping

def resolve_category_id(title, tags, product_type, template_type, mapping):
    """Resolve eBay category ID using mapping rules.

    Priority:
    1) by_template
    2) by_type_equals (exact match on Shopify Type)
    3) by_tag_contains (substring match on tags)
    4) by_title_contains (substring match on title)
    5) default
    """
    title_l = (title or '').lower()
    tags_l = (tags or '').lower()
    type_l = (product_type or '').lower()

    # 1) template
    cat = (mapping.get('by_template') or {}).get(template_type)
    if cat:
        return cat

    # 2) exact type match
    for t, cid in (mapping.get('by_type_equals') or {}).items():
        if type_l == (t or '').lower():
            return cid

    # 3) tag contains
    for kw, cid in (mapping.get('by_tag_contains') or {}).items():
        if (kw or '').lower() in tags_l:
            return cid

    # 4) title contains
    for kw, cid in (mapping.get('by_title_contains') or {}).items():
        if (kw or '').lower() in title_l:
            return cid

    # 5) default
    return mapping.get('default', '7317')

def main():
    """
    Main function to process the Shopify export and convert it to an eBay import file.
    """
    print("Starting script...")
    input_file = 'products_export_1.csv'
    output_file = 'ebay_import.csv'

    # Configuration via environment variables
    try:
        price_markup = float(os.getenv('PRICE_MARKUP_EUR', '1.50'))
    except ValueError:
        price_markup = 1.50
    # Minimum start price filter (in EUR). Variants below are skipped.
    try:
        min_price_eur = float(os.getenv('MIN_PRICE_EUR', '3.00'))
    except ValueError:
        min_price_eur = 3.00
    # Force a fixed quantity for all variants; set to '' to disable
    fixed_quantity_env = os.getenv('FIXED_QUANTITY', '3')
    try:
        fixed_quantity = int(fixed_quantity_env) if fixed_quantity_env != '' else None
    except ValueError:
        fixed_quantity = 3

    # Default back to using eBay business policies for shipping
    use_shipping_profile = os.getenv('USE_SHIPPING_PROFILE', '1') == '1'
    use_return_profile = os.getenv('USE_RETURN_PROFILE', '0') == '1'
    policy_payment_name = os.getenv('POLICY_PAYMENT_NAME', 'eBay Managed Payments (238923344012)')
    policy_shipping_name = os.getenv('POLICY_SHIPPING_NAME', 'Paket')
    policy_return_name = os.getenv('POLICY_RETURN_NAME', '30 Tage Rückgabe')
    shipping_type = os.getenv('SHIPPING_TYPE', 'Flat')
    shipping_service_option = os.getenv('SHIPPING_SERVICE_OPTION', 'DE_Warensendung')
    try:
        shipping_cost = float(os.getenv('SHIPPING_COST_EUR', '1.95'))
    except ValueError:
        shipping_cost = 1.95
    try:
        shipping_additional_cost = float(os.getenv('SHIPPING_ADDITIONAL_COST_EUR', '0.00'))
    except ValueError:
        shipping_additional_cost = 0.00

    pickup_enabled = os.getenv('PICKUP_ENABLED', '1') == '1'
    pickup_service_option = os.getenv('PICKUP_SERVICE_OPTION', 'LocalPickup')
    try:
        pickup_cost = float(os.getenv('PICKUP_COST_EUR', '0.00'))
    except ValueError:
        pickup_cost = 0.00
    pickup_address = os.getenv('PICKUP_ADDRESS', 'Stadtweide 24, 23562 Lübeck')
    # Listing location fields
    location_city = os.getenv('LOCATION_CITY', 'Lübeck')
    postal_code = os.getenv('POSTAL_CODE', '23562')
    country = os.getenv('COUNTRY', 'DE')

    templates = {}
    for tpl_name in ["wuerfelsets", "wuerfel", "wuerfelzubehoer", "spiel"]:
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
                        'variant_keys': set(),
                        'images': set()
                    }

                # Build a deduplication key for variants
                sku = (row.get('Variant SKU') or '').strip()
                barcode = (row.get('Variant Barcode') or '').strip()
                opt1 = (row.get('Option1 Value') or '').strip()
                opt2 = (row.get('Option2 Value') or '').strip()
                opt3 = (row.get('Option3 Value') or '').strip()
                if sku:
                    vkey = f"sku:{sku}"
                elif barcode:
                    vkey = f"barcode:{barcode}"
                else:
                    vkey = f"opts:{opt1}|{opt2}|{opt3}"

                if vkey not in products[handle]['variant_keys']:
                    products[handle]['variants'].append({
                        'Variant Price': row['Variant Price'],
                        'Variant SKU': row['Variant SKU'],
                        'Variant Inventory Qty': row['Variant Inventory Qty'],
                        'Variant Barcode': row.get('Variant Barcode', ''),
                        'Option1 Value': opt1,
                        'Option2 Value': opt2,
                        'Option3 Value': opt3
                    })
                    products[handle]['variant_keys'].add(vkey)

                if row['Image Src']:
                    products[handle]['images'].add(row['Image Src'])
        print(f"Finished reading {input_file}. Found {len(products)} products.")

    except FileNotFoundError:
        print(f"Error: The file {input_file} was not found.")
        return
    except Exception as e:
        print(f"An unexpected error occurred during file reading: {e}")
        return

    # Load category mapping
    category_mapping = load_category_mapping()

    # Base headers (common)
    ebay_headers = [
        '*Action', '*Category', '*Title', '*Description', '*ConditionID',
        '*Format', '*Duration', '*StartPrice', '*Quantity', 'PicURL',
        'CustomLabel', 'Product:Brand', 'Location', 'Product:MPN', 'C:Marke',
        '*DispatchTimeMax'
    ]

    if use_shipping_profile:
        # Business policies mode: add policy fields
        ebay_headers += ['PaymentProfileName', 'ShippingProfileName']
        if use_return_profile:
            ebay_headers += ['ReturnProfileName']
        else:
            ebay_headers += [
                '*ReturnsAcceptedOption', '*ReturnsWithinOption',
                '*RefundOption', '*ShippingCostPaidByOption'
            ]
    else:
        # Flat shipping mode: add explicit shipping columns
        ebay_headers += [
            'ShippingType',
            'ShippingService-1:Option',
            'ShippingService-1:Cost',
            'ShippingService-1:Priority',
            'ShippingService-1:AdditionalCost',
            'ShippingService-1:FreeShipping',
            'ShippingService-2:Option',
            'ShippingService-2:Cost',
            'ShippingService-2:Priority',
            'ShippingService-2:AdditionalCost',
            'ShippingService-2:FreeShipping'
        ]
        ebay_headers += [
            '*ReturnsAcceptedOption', '*ReturnsWithinOption',
            '*RefundOption', '*ShippingCostPaidByOption'
        ]

    # Encourage account-level combined shipping discounts
    ebay_headers += ['ApplyShippingDiscount']
    # Common location/shipping scope fields
    ebay_headers += ['PostalCode', 'Country', 'ShipToLocations']

    print(f"Writing to {output_file}...")
    # Test mode: limit to one product per category if env var is set
    limit_one_per_category = os.getenv('LIMIT_ONE_PER_CATEGORY', '0') == '1'
    seen_categories = set()

    # Optional: limit number of exported products (distinct products), include all their variants
    try:
        limit_products = int(os.getenv('LIMIT_PRODUCTS', '0'))
    except ValueError:
        limit_products = 0
    exported_products = 0

    with open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=ebay_headers)
        writer.writeheader()
        seen_custom_labels = {}

        for handle, product_data in products.items():
            if product_data['Status'].lower() != 'active':
                continue

            print(f"Processing product: {product_data['Title']}")

            template_type = get_template_type(product_data['Title'], product_data['Tags'])
            template_str = templates[template_type]
            
            parsed_details = parse_html_description(product_data['Body (HTML)'])

            image_urls = '|'.join(product_data['images'])
            main_image = next(iter(product_data['images']), '')

            # Resolve category ID
            category_id = resolve_category_id(
                product_data['Title'],
                product_data['Tags'],
                product_data['Type'],
                template_type,
                category_mapping
            )

            # If test limit is enabled, only allow the first product per category
            if limit_one_per_category:
                if category_id in seen_categories:
                    print(f"Skipping due to LIMIT_ONE_PER_CATEGORY for category {category_id}")
                    continue
                seen_categories.add(category_id)

            wrote_variant = False
            for variant in product_data['variants']:
                if fixed_quantity is None:
                    if not variant['Variant Inventory Qty'] or int(variant['Variant Inventory Qty']) <= 0:
                        continue

                description_line_1 = product_data['Body (HTML)'].split('</p>')[0].replace('<p>','')

                # Calculate adjusted price
                try:
                    base_price = float(str(variant['Variant Price']).replace(',', '.'))
                except ValueError:
                    base_price = 0.0
                adjusted_val = base_price + price_markup
                # Skip variants below minimum price
                if adjusted_val < min_price_eur:
                    print(f"Skipping variant below min price: {product_data['Title']} @ {adjusted_val:.2f} EUR")
                    continue
                adjusted_price = f"{adjusted_val:.2f}"

                # eBay title must be <= 80 chars
                ebay_title = truncate_title(product_data['Title'], 80)

                context = {
                    'title': product_data['Title'],
                    'price': adjusted_price,
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
                # Add pickup and combined-shipping info to description
                extra_blocks = []
                if pickup_enabled:
                    extra_blocks.append(
                        f"<p><strong>Abholung möglich:</strong> {pickup_address}<br><small><em>Öffnungszeiten: Di–Sa 13–18 Uhr</em></small></p>"
                    )
                # Mention combined shipping
                if shipping_additional_cost <= 0:
                    extra_blocks.append(
                        "<p><strong>Kombiversand:</strong> Beim Kauf mehrerer Artikel zahlen Sie keine zusätzlichen Versandkosten (0,00 EUR) pro weiterem Artikel.</p>"
                    )
                else:
                    extra_blocks.append(
                        f"<p><strong>Kombiversand:</strong> Beim Kauf mehrerer Artikel zahlen Sie nur {shipping_additional_cost:.2f} EUR zusätzlich pro weiterem Artikel.</p>"
                    )
                if extra_blocks:
                    final_description = final_description + "\n" + "\n".join(extra_blocks)

                # Ensure MPN present to satisfy BrandMPN pairing
                raw_mpn = (variant['Variant SKU'] or '').strip()
                mpn_value = raw_mpn if raw_mpn else 'Does not apply'

                # Build a robust CustomLabel
                def _slug(s: str) -> str:
                    import re as _re
                    return _re.sub(r'[^a-z0-9]+','-', (s or '').lower()).strip('-')
                if (variant['Variant SKU'] or '').strip():
                    custom_label = variant['Variant SKU']
                else:
                    parts = [_slug(handle), _slug(variant.get('Option1 Value','')), _slug(variant.get('Option2 Value','')), _slug(variant.get('Option3 Value',''))]
                    parts = [p for p in parts if p]
                    custom_label = '-'.join(parts) if parts else _slug(handle)

                # Ensure CustomLabel uniqueness by suffixing on duplicates
                base = custom_label
                if base in seen_custom_labels:
                    seen_custom_labels[base] += 1
                    custom_label = f"{base}-dup{seen_custom_labels[base]}"
                else:
                    seen_custom_labels[base] = 1

                ebay_row = {
                    '*Action': 'VerifyAdd',
                    '*Category': category_id,
                    '*Title': ebay_title,
                    '*Description': final_description,
                    '*ConditionID': '1000',
                    '*Format': 'FixedPrice',
                    '*Duration': 'GTC',
                    '*StartPrice': adjusted_price,
                    '*Quantity': str(fixed_quantity if fixed_quantity is not None else variant['Variant Inventory Qty']),
                    'PicURL': image_urls,
                    'CustomLabel': custom_label,
                    'Product:Brand': product_data['Vendor'],
                    'Location': location_city,
                    'Product:MPN': mpn_value,
                    'C:Marke': product_data['Vendor'],
                    '*DispatchTimeMax': '2',
                    'ApplyShippingDiscount': '1',
                    'PostalCode': postal_code,
                    'Country': country,
                    'ShipToLocations': country
                }

                # Populate profile fields or flat shipping fields
                if use_shipping_profile:
                    ebay_row.update({
                        'PaymentProfileName': policy_payment_name,
                        'ShippingProfileName': policy_shipping_name,
                    })
                    if use_return_profile:
                        ebay_row.update({'ReturnProfileName': policy_return_name})
                    else:
                        ebay_row.update({
                            '*ReturnsAcceptedOption': 'ReturnsAccepted',
                            '*ReturnsWithinOption': 'Days_30',
                            '*RefundOption': 'MoneyBack',
                            '*ShippingCostPaidByOption': 'Buyer'
                        })
                else:
                    ebay_row.update({
                        'ShippingType': shipping_type,
                        'ShippingService-1:Option': shipping_service_option,
                        'ShippingService-1:Cost': f"{shipping_cost:.2f}",
                        'ShippingService-1:Priority': '1',
                        'ShippingService-1:AdditionalCost': f"{shipping_additional_cost:.2f}",
                        'ShippingService-1:FreeShipping': 'FALSE',
                    })
                    if pickup_enabled:
                        ebay_row.update({
                            'ShippingService-2:Option': pickup_service_option,
                            'ShippingService-2:Cost': f"{pickup_cost:.2f}",
                            'ShippingService-2:Priority': '2',
                            'ShippingService-2:AdditionalCost': f"{pickup_cost:.2f}",
                            'ShippingService-2:FreeShipping': 'TRUE',
                        })
                    ebay_row.update({
                        '*ReturnsAcceptedOption': 'ReturnsAccepted',
                        '*ReturnsWithinOption': 'Days_30',
                        '*RefundOption': 'MoneyBack',
                        '*ShippingCostPaidByOption': 'Buyer'
                    })
                writer.writerow(ebay_row)
                wrote_variant = True

            if wrote_variant:
                exported_products += 1
                if limit_products and exported_products >= limit_products:
                    print(f"Reached LIMIT_PRODUCTS={limit_products}. Stopping.")
                    break

    print(f"\nProcessing complete. The eBay import file has been saved to {output_file}")

if __name__ == "__main__":
    main()
