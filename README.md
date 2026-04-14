# EbayImporterAI

Konvertiert Shopify-Produkt-Exporte (`products_export_1.csv`) in eBay File-Exchange CSV (`ebay_import.csv`) mit gerenderten HTML-Beschreibungen und konfigurierbaren Versand-/Rücknahme-Optionen.

## Schnellstart
- CSV in den Projektordner legen: `products_export_1.csv`
- Empfehlenswert: eBay-Policy-Namen setzen (exakte Namen aus dem Seller Hub):
  - `POLICY_PAYMENT_NAME`, `POLICY_SHIPPING_NAME`
- Ausführen: `python main.py`
- Ergebnis: `ebay_import.csv`

## Wichtige Funktionen
- Templates: `vorlage_wuerfelsets.html`, `vorlage_wuerfel.html`, `vorlage_wuerfelzubehoer.html`, `vorlage_spiel.html` (neutral für Nicht‑Würfel‑Produkte).
- Varianten-Deduplizierung: Zusammenfassung je Produkt über `SKU → Barcode → Optionskombination`.
- Titel-Check: `*Title` wird automatisch auf 80 Zeichen gekürzt.
- Preise: Aufschlag per `PRICE_MARKUP_EUR` (Default 1.50).
- Mindestpreis: Varianten unter `MIN_PRICE_EUR` (Default 3.00) werden übersprungen.
- Menge: Feste Menge via `FIXED_QUANTITY` (Default 3). Leer lassen, um Shopify-Bestand (>0) zu verwenden.
- Versand: Standardmäßig eBay‑Business‑Policies (`PaymentProfileName`, `ShippingProfileName`). Flat‑Versand optional.
- Rücknahme: Standardmäßig explizit per Feldern (`*ReturnsAcceptedOption` etc.). Alternativ via `ReturnProfileName`.
- Abholung & Kombiversand: Optionaler LocalPickup, `ApplyShippingDiscount=1` gesetzt (Konto‑Rabatte im Seller Hub aktivieren).
- Standort: `Location` (Stadt), `PostalCode`, `Country`, `ShipToLocations` gesetzt.
- Labels/MPN: `CustomLabel` eindeutig; `Product:MPN` = SKU oder „Does not apply“.

## Umgebungsvariablen (Auszug)
- Policies: `USE_SHIPPING_PROFILE=1` (Default), `USE_RETURN_PROFILE=0`, `POLICY_PAYMENT_NAME`, `POLICY_SHIPPING_NAME`, `POLICY_RETURN_NAME`.
- Preise/Mengen: `PRICE_MARKUP_EUR=1.50`, `MIN_PRICE_EUR=3.00`, `FIXED_QUANTITY=3`.
- Flat-Versand (bei `USE_SHIPPING_PROFILE=0`): `SHIPPING_TYPE=Flat`, `SHIPPING_SERVICE_OPTION`, `SHIPPING_COST_EUR`, `SHIPPING_ADDITIONAL_COST_EUR` (Default 0.00), `PICKUP_ENABLED=1`, `PICKUP_SERVICE_OPTION=LocalPickup`, `PICKUP_COST_EUR=0.00`.
- Standort: `PICKUP_ADDRESS`, `LOCATION_CITY`, `POSTAL_CODE`, `COUNTRY`.
- Tests: `LIMIT_ONE_PER_CATEGORY=1`, `LIMIT_PRODUCTS=N`.

## Troubleshooting (häufig)
- Fehler 37 ShippingDetails: Policies nutzen und Namen exakt setzen, Flat‑Feldern nur bei `USE_SHIPPING_PROFILE=0`.
- Fehler 37 BrandMPN: `Product:Brand` gesetzt und `Product:MPN` auf SKU oder „Does not apply“.
- Fehler 70 Title >80: Titel werden automatisch gekürzt.
- Rücknahme‑Warnung: eBay kann `RefundOption` je Kategorie ignorieren (Listing verifiziert dennoch).
- Kombiversand addiert für verschiedene Listings: Konto‑Rabattschema im Seller Hub aktivieren (`ApplyShippingDiscount=1`).

Weitere Details, Heuristiken und Felder siehe `agents.md`.
