# IdoSell — stany magazynowe i ceny zestawów

Aplikacja Windows dla kartony24h.com. Wyszukuje produkt po kodzie zewnętrznym, pozwala ustawić stan magazynowy oraz pobrać wszystkie przypisane zestawy i zmienić ich podstawowe ceny detaliczne brutto. Pokazuje liczbę sztuk oraz cenę brutto za sztukę.

## Instalacja

1. Zainstaluj Python 3.10 lub nowszy z https://www.python.org/downloads/windows/. W instalatorze pozostaw Python Launcher oraz Tcl/Tk (Tkinter).
2. Pobierz repozytorium: Code → Download ZIP, a następnie rozpakuj cały ZIP do folderu, w którym masz prawo zapisu.
3. Uruchom `Uruchom.cmd`.
4. Kliknij „Importuj klucz API…” i wybierz plik tekstowy zawierający wyłącznie klucz API IdoSell dla kartony24h.com.

Nie są potrzebne pakiety pip, Codex ani Hoshi. Alternatywnie uruchom `python app.py` w folderze programu.

Klucz wymaga PIM → odczyt i zapis: GET products/products, PUT products/stockQuantity i PUT products/products (API v8). Konfiguracja gospodarki magazynowej sklepu musi pozwalać na bezpośrednią zmianę stanów.

Klucz jest przechowywany lokalnie w `data/api-key.dpapi`, zaszyfrowany przez Windows DPAPI dla danego konta użytkownika. Na innym komputerze zaimportuj go ponownie. Nie dodawaj kluczy ani katalogu data do repozytorium.

## Użycie

- Stan: wpisz kod zewnętrzny, wyszukaj, wybierz magazyn, wpisz docelową ilość i zatwierdź. Nowa ilość zastępuje stan.
- Zestawy: po wpisaniu kodu składnika kliknij „Pobierz wszystkie zestawy produktu”. Lista uwzględnia także niewidoczne zestawy.
- Zaznacz jedną lub kilka pozycji (Ctrl/Shift) albo wszystkie. Wpisana cena brutto dotyczy całego zestawu; ta sama kwota jest ustawiana dla wszystkich zaznaczonych pozycji. Różne ceny zapisuj osobno.
- Liczba sztuk pochodzi ze składu zestawu. Cena za sztukę jest ilorazem ceny zestawu i sumy ilości składników, wyświetlanym do czterech miejsc po przecinku. Dla zestawów mieszanych to średnia na sztukę wszystkich składników.

Program ponownie odczytuje dane przed zapisem i weryfikuje wynik po zapisie. Operacje nie są transakcją: inne integracje mogą równocześnie zmieniać dane. W przypadku błędu seria zapisów cen zatrzymuje się; potwierdzone zmiany nie są cofane. Automatyczne reguły cenowe w sklepie nie są wyłączane. Cena podstawowa nie jest ceną promocyjną ani ceną konkretnej oferty Allegro.

## Sprawdzenie

`py -3 -m unittest discover -v`

Testy lokalne obejmują dopasowanie kodu, zmianę danych przed zapisem, odczyt potwierdzający, kompletność zestawów i obliczanie cen jednostkowych. Odczyt zestawów oraz zapis stanu produktu testowego sprawdzono na sklepie. Zapis cen zestawów testowano na symulowanym API. Integracja z BaseLinkerem/Allegro nie jest zaimplementowana.
