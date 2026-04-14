# EbayImporterAI – Projektüberblick und Arbeitsablauf

Dieser Leitfaden beschreibt Zweck, Aufbau und Arbeitsabläufe des Projekts. Ziel ist es, Shopify-Produkt-Exporte in eBay-Importdateien (File Exchange) zu konvertieren. Eine geplante KI-Anreicherung über Bilder wurde verworfen und ist aktuell deaktiviert. Die HTML-Templates sind noch nicht final.

**Kernidee**
- Eingabe: Shopify-Export (`products_export_1.csv`).
- Verarbeitung: Varianten/Bilder je Produkt zusammenfassen, HTML-Template wählen, Beschreibung rendern, eBay-CSV schreiben.
- Ausgabe: `ebay_import.csv` nach File-Exchange-Schema, inkl. fertigem HTML.

**Dateien & Struktur**
- `main.py`: Orchestriert die Konvertierung, Optionen per Umgebungsvariablen.
- `vorlage_wuerfelsets.html`, `vorlage_wuerfel.html`, `vorlage_wuerfelzubehoer.html`, `vorlage_spiel.html`: HTML-Templates.
- `products_export_1.csv`: Shopify-Export.
- `ebay_import.csv`: Ergebnisdatei.
- `category_mapping.json`: Kategorienregeln (by_template/by_type_equals/by_tag_contains/by_title_contains/default).
- `Anleitungen/`: eBay-Dokumente (File Exchange), ConditionIDs.
- `gemini.md`: (inaktiv) Ideen für KI-Enrichment.

**Datenfluss (vereinfacht)**
- Import Shopify-CSV; Gruppierung nach `Handle` (Produkt) mit Varianten + Image-URLs.
- Deduplizierung Varianten pro Produkt: Schlüsselreihenfolge `SKU` → `Barcode` → Optionskombination.
- Template-Wahl per Heuristik:
  - Zubehör: „beutel, schale, tasche, box, turm, becher, würfelbrett, einlage, tower, tray, bag“ → `wuerfelzubehoer`.
  - Enthält Würfel-Kürzel (z. B. „w6“, „d20“) → `wuerfel`.
  - Enthält „set“ → `wuerfelsets`.
  - Fallback → `spiel` (neutrales Template ohne „Würfel sind hochwertig …“).
- Extraktion einfacher Details aus `Body (HTML)` via Regex: `Material:`, `Farbe:`, `Lieferumfang:` und erste Satzzeile (Kurzbeschreibung).
- Beschreibung rendern, eBay-Zeile je Variante schreiben (Mengenregel siehe unten).

**eBay-Felder – aktuell**
- Listing: `*Action`, `*Category`, `*Title` (≤80 Zeichen, wird automatisch gekürzt), `*Description`, `*ConditionID`, `*Format`, `*Duration`, `*StartPrice`, `*Quantity`, `PicURL`, `CustomLabel`, `Product:Brand`, `Product:MPN` (SKU oder „Does not apply“), `C:Marke`, `Location` (Stadt), `PostalCode`, `Country`, `ShipToLocations`, `*DispatchTimeMax`.
- Rücknahme: explizit via `*ReturnsAcceptedOption`, `*ReturnsWithinOption`, `*RefundOption`, `*ShippingCostPaidByOption` (Warnungen möglich, aber unkritisch), oder alternativ via `ReturnProfileName` (wenn konfiguriert).
- Versand: Standardmäßig Business-Policies aktiv (`PaymentProfileName`, `ShippingProfileName`). Flat-Versand ist optional möglich (ShippingType/Services), wird aber nur genutzt, wenn explizit aktiviert.
- Kombiversand: `ApplyShippingDiscount=1`. Für artikelübergreifende Rabatte eBay-Konto-Rabatte hinterlegen.

**Konfiguration (Umgebungsvariablen)**
- Preise: `PRICE_MARKUP_EUR` (Default 1.50).
- Menge: `FIXED_QUANTITY` (Default 3; leer lassen, um Shopify-Bestand zu nutzen und ≤0 zu filtern).
- Mindestpreis: `MIN_PRICE_EUR` (Default 3.00) – Varianten darunter werden übersprungen.
- Policies: `USE_SHIPPING_PROFILE=1` (Default), `USE_RETURN_PROFILE=0`.
  - `POLICY_PAYMENT_NAME`, `POLICY_SHIPPING_NAME`, optional `POLICY_RETURN_NAME` (exakte Namen aus eBay).
- Flat-Versand (nur wenn `USE_SHIPPING_PROFILE=0`): `SHIPPING_TYPE=Flat`, `SHIPPING_SERVICE_OPTION`, `SHIPPING_COST_EUR`, `SHIPPING_ADDITIONAL_COST_EUR` (Default 0.00), `PICKUP_ENABLED=1`, `PICKUP_SERVICE_OPTION=LocalPickup`, `PICKUP_COST_EUR=0.00`.
- Abholung/Standort: `PICKUP_ADDRESS` (für Beschreibung), `LOCATION_CITY` (Location-Feld), `POSTAL_CODE`, `COUNTRY`.
- Tests: `LIMIT_ONE_PER_CATEGORY=1`, `LIMIT_PRODUCTS=N`.

**Nutzung**
1) `products_export_1.csv` ins Projekt-Root legen.
2) Templates bei Bedarf anpassen (`vorlage_*.html`). Platzhalter u. a.: `{title}`, `{price}`, `{image_url}`, `{short_description}`, `{brand}`, `{detailed_title}`, `{description_line_1}`, `{material}`, `{color}`, `{delivery_scope}`, `{warning_html}`.
3) Policies (empfohlen): `POLICY_PAYMENT_NAME`, `POLICY_SHIPPING_NAME` setzen. Ausführen: `python main.py`.
4) Ergebnis prüfen: `ebay_import.csv` (Titel ≤80, Menge, Preise, Beschreibung, Standort, Versand/Rücknahme-Felder).

**Wichtige Regeln/Details**
- Titel werden automatisch auf 80 Zeichen gekürzt (Wortgrenze, wenn möglich).
- Varianten-Deduplizierung: Kein Duplikat durch Bildzeilen im Shopify-Export.
- `CustomLabel` eindeutig: SKU, sonst Slug aus Handle/Optionen; Duplikate werden mit `-dupN` suffigiert.
- `Product:MPN`: SKU oder „Does not apply“ (gegen BrandMPN-Fehler).
- Neutrales Template (`spiel`) für Nicht-Würfel-Produkte (kein Würfel-Qualitätsabsatz, kein oberer Marken-Header; Marken-Footer bleibt).
- Mindestpreis-Filter: Varianten unter `MIN_PRICE_EUR` (nach Aufschlag) werden übersprungen.

**Troubleshooting**
- Fehler 37 (ShippingDetails/BrandMPN): Versand-Policies statt Flat nutzen; Policy-Namen exakt setzen. Bei BrandMPN sicherstellen, dass MPN gesetzt ist (oder „Does not apply“).
- Fehler 70 (Titel > 80): Titel werden jetzt automatisch gekürzt.
- Rücknahme-Warnung (Refund ignoriert): unkritisch; eBay kann Kategorie-bedingt Optionen ignorieren.
- Kombiversand addiert bei verschiedenen Listings: Konto-Rabatte im Seller Hub konfigurieren (ApplyShippingDiscount ist gesetzt).
- Leere Ausgabe: Prüfen `Status` = active, `Variant Inventory Qty` > 0 (sofern `FIXED_QUANTITY` leer), Mindestpreis-Filter.

**Nächste Schritte (Empfehlung)**
- Kategorien-Mapping verfeinern; Item-Specifics ergänzen.
- Templates finalisieren und konsolidieren.
- Optional: Robustere Parser (HTML) und Previews.
