# EbayImporterAI – Projektüberblick und Arbeitsablauf

Dieser Leitfaden beschreibt Zweck, Aufbau und Arbeitsabläufe des Projekts. Ziel ist es, Shopify-Produkt-Exporte in eBay-Importdateien (File Exchange) zu konvertieren. Eine geplante KI-Anreicherung über Bilder wurde verworfen und ist aktuell deaktiviert. Die HTML-Templates sind noch nicht final.

**Kernidee**
- Eingabe: Shopify-Export (`products_export_1.csv`).
- Verarbeitung: Zusammenfassen von Varianten/Bildern pro Produkt, Auswählen einer HTML-Beschreibungsvorlage, Befüllen der Vorlage mit Produktdetails.
- Ausgabe: eBay-Import-CSV (`ebay_import.csv`) nach File-Exchange-Schema, inkl. fertig gerenderter HTML-Beschreibung.

**Dateien & Struktur**
- `main.py`: Python-Skript, das die gesamte Konvertierung ausführt.
- `vorlage_wuerfelsets.html`, `vorlage_wuerfel.html`, `vorlage_wuerfelzubehoer.html`: HTML-Templates für die eBay-Beschreibung.
- `products_export_1.csv`: Beispiel-/Eingabe-Export aus Shopify (Spalten wie `Handle`, `Title`, `Body (HTML)`, `Vendor`, `Type`, `Tags`, `Variant Price`, `Variant SKU`, `Variant Inventory Qty`, `Image Src`, `Status`).
- `ebay_import.csv`: Generierte eBay-Importdatei (Ergebnis).
- `Anleitungen/`: Offizielle eBay-Dokumente (File Exchange) und Kategorien/Condition-IDs zur Referenz.
- `gemini.md`: Ursprünglicher Plan für eine KI-gestützte Variante (derzeit nicht aktiv).

**Datenfluss (vereinfacht)**
- Einlesen des Shopify-Exports; Gruppierung nach `Handle` zu Produkten mit Varianten und Bild-URLs.
- Template-Wahl anhand Titel/Tags (Heuristik):
  - Zubehör: „beutel, schale, tasche, box, turm, becher, würfelbrett, einlage, tower, tray, bag“ → `wuerfelzubehoer`.
  - Enthält „set“ im Titel/Tag → `wuerfelsets`.
  - Enthält Würfel-Kürzel (z. B. „w6“, „d20“) → `wuerfel`.
  - Fallback → `wuerfelsets`.
- Extraktion einfacher Details aus `Body (HTML)` via Regex:
  - `Material:`, `Farbe:`, `Lieferumfang:` sowie erste Satzzeile als Kurzbeschreibung.
- Rendern der HTML-Beschreibung per Template-Variablen und Schreiben einer eBay-CSV-Zeile pro aktiver Variante mit Bestand > 0.

**Erzeugte eBay-Felder (Stand: Code)**
- Pflicht/Listing: `*Action` (VerifyAdd), `*Category` (derzeit fest `7317`), `*Title`, `*Description` (gerendertes HTML), `*ConditionID` (1000), `*Format` (FixedPrice), `*Duration` (GTC), `*StartPrice`, `*Quantity`, `PicURL` (alle Bilder per `|` getrennt), `CustomLabel` (SKU/Handle), `Product:Brand`, `Location`, `Product:MPN`, `C:Marke`, `PaymentProfileName`, `ShippingProfileName`, `ReturnProfileName`.
- Hinweis: Einige eBay-/File-Exchange-Felder aus den PDFs (z. B. `*DispatchTimeMax`, `*ReturnsAcceptedOption`) sind aktuell nicht enthalten. Bitte gegen die Vorgaben im Ordner `Anleitungen` prüfen und bei Bedarf ergänzen.

**Nutzung**
1) Shopify-Export als `products_export_1.csv` im Projektroot ablegen.
2) Templates bei Bedarf anpassen (`vorlage_*.html`). Platzhalter sind u. a.: `{title}`, `{price}`, `{image_url}`, `{short_description}`, `{brand}`, `{detailed_title}`, `{description_line_1}`, `{material}`, `{color}`, `{delivery_scope}`, `{warning_html}`.
3) Skript ausführen: `python main.py`.
4) Ergebnis prüfen: `ebay_import.csv` und stichprobenartig die HTML-Beschreibungen (z. B. per eBay-Vorschau/Tool).

**Konfiguration & Stellen zum Anpassen**
- Eingabe-/Ausgabedateien: in `main.py` (`input_file`, `output_file`).
- eBay-Kategorie: `*Category` ist aktuell fix auf `7317` gesetzt. Für produktgenaue Kategorien eine Mapping-Tabelle (z. B. CSV/JSON) einführen.
- Profile/Standort: `PaymentProfileName`, `ShippingProfileName`, `ReturnProfileName`, `Location` in `main.py` an die eigenen eBay-Kontodaten anpassen.
- Template-Heuristik: Funktion `get_template_type(...)` – Keywords/Regeln an Sortiment anpassen.
- Detail-Parsing: Funktion `parse_html_description(...)` – Regex/Labels (Material/Farbe/Lieferumfang) erweitern/robuster machen.

**Grenzen & TODOs**
- Templates: „noch nicht final“. Inhalt/Design zentral in `vorlage_*.html` pflegen und vereinheitlichen.
- Kategorien: Aktuell hart codiert; eine robuste Zuordnung basierend auf Shopify-Typ/Tags ist offen.
- eBay-Compliance: Gegen die PDFs in `Anleitungen/` validieren; ggf. weitere Pflichtfelder ergänzen (z. B. Versandzeit, Rücknahmeoptionen, Artikelmerkmale/Item Specifics).
- HTML-Parsing: Regex ist fragil gegenüber uneinheitlichem HTML/Text; eventuell HTML parser (z. B. `BeautifulSoup`) verwenden.
- Varianten/Bestände: Nur aktive Produkte; Varianten mit Bestand ≤ 0 werden übersprungen – Logik passt, aber ggf. konfigurierbar machen.

**Abgebrochene KI-Funktion (Hinweis)**
- Geplant war eine Bildanalyse (z. B. Material/Farbe aus Produktbildern), um Beschreibung/Attribute anzureichern. Diese Funktionalität ist aktuell entfernt/deaktiviert.
- Wenn später gewünscht: Separates Enrichment-Modul mit Bild-KI (lokal/Cloud) entwickeln, Ergebnisse als zusätzliche Felder ins Template einspeisen. Wichtig: deterministische Fallbacks und manuelle Überschreibungen ermöglichen.

**Troubleshooting**
- Leeres Ergebnis/zu wenige Zeilen: Prüfen, ob `Status` in Shopify „active“ ist und `Variant Inventory Qty` > 0.
- Fehlende Templates: Konsolen-Output prüfen („FATAL: Template file … not found.“); Dateien/Dateinamen im Root vorhanden?
- Falsche Template-Wahl: Keywords/Tags in `get_template_type(...)` erweitern oder hart zuweisen (Sonderfälle über Mapping).
- eBay-Importfehler: Import-Report von eBay und die PDFs im Ordner `Anleitungen/` heranziehen; Feldliste im Code angleichen.

**Nächste Schritte (Empfehlung)**
- Kategorien-Mapping implementieren; Item-Specifics ergänzen.
- Templates finalisieren und konsolidieren; Platzhalter dokumentieren.
- Robustere Parser einführen; Validierung/Previews in den Build integrieren.
- Optional: KI-Enrichment als separates opt-in Modul reaktivieren.

