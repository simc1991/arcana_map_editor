# Arcana Map Studio

Éditeur open source de cartes et outils d’analyse pour **Arcana (USA)** sur Super Nintendo.

## État actuel

La version `0.7.1` fournit :

- validation du ROM LoROM d’Arcana USA, avec ou sans en-tête copieur de 512 octets ;
- lecture de l’en-tête SNES, SHA-256 et CRC32 ;
- décompression native du format HAL utilisé par le jeu ;
- extraction des 34 entrées de donjon et des 14 blocs de cartes 32×32 uniques ;
- espace de travail inspiré de RPG Maker XP avec explorateur, barre d’outils, palette et inspecteur ;
- rendu top-down WYSIWYG de la logique du jeu avec sols, murs, rencontres, brouillard, escaliers, coffres et événements ;
- aperçu In-Game en perspective à la première personne, synchronisé avec la carte 2D ;
- navigation dans le donjon avec `W/S`, rotation avec `A/D` et orientation visible sur le plan ;
- murs en perspective, profondeur, briques, couloirs et marqueurs interactifs dans l’aperçu ;
- zoom de 50 à 200 %, grille et affichage optionnel des valeurs techniques ;
- outils crayon, rectangle, remplissage, pipette et historique annuler/rétablir ;
- explorateur structuré par chapitre et panneau listant tous les éléments interactifs de la carte ;
- éditeur d’événements complet par onglets Général, Gameplay et Notes ;
- noms personnalisés, déplacement, changement de type et variantes sans manipulation hexadécimale obligatoire ;
- propriétés adaptées au contexte : contenu de coffre, destination, orientation, groupe de rencontres, fréquence, condition et déclenchement ;
- catalogue de coffre décodé depuis le ROM avec 145 entrées : monnaie, objets, armes, armures, boucliers, accessoires et cartes ;
- sélecteur d’objet recherchable affichant le nom, la catégorie et l’identifiant du jeu ;
- Base de données d’objets façon RPG Maker avec recherche et filtres ;
- modification, duplication et création d’objets conservées dans le projet ;
- statistiques d’équipement éditables : attaque, défense, défense magique et caractéristiques ;
- attaque des armes, défense des armures/boucliers/accessoires et défense magique décodées depuis les tables du ROM ;
- restrictions d’équipement originales décodées par personnage ;
- champs non pertinents automatiquement désactivés selon la catégorie ;
- prix d’achat et valeur de revente décodés depuis le ROM pour les équipements ;
- restrictions d’équipement par personnage et affectation aux vendeurs par chapitre ;
- nouveaux objets immédiatement disponibles dans le sélecteur des coffres ;
- recherche instantanée, création, duplication, suppression et navigation vers les événements ;
- validation des positions, variantes et collisions entre événements ;
- édition sémantique des rencontres, transitions, coffres et événements encodés dans les tuiles ;
- explication des variantes, tables de rencontres et fréquences réelles `1/12` ou `1/4` dans l’inspecteur ;
- prise en compte des cartes partagées entre plusieurs étages de Stavery ;
- sauvegarde non destructive dans un projet JSON rétrocompatible avec les versions 0.1, 0.2 et 0.3 ;
- compresseur HAL compatible avec les commandes utilisées par les cartes ;
- reconstruction et relocation automatique des 14 blocs de cartes dans la banque `$13` ;
- mise à jour des 34 pointeurs de cartes et du checksum SNES ;
- export non destructif vers un nouveau fichier `.sfc` avec vérification par redécompression ;
- injection des types, identifiants, quantités et nouvelles positions des coffres existants ;
- décodage des tables d’escaliers, y compris la case d’activation adjacente ;
- injection des cartes cibles, coordonnées et orientations des escaliers internes existants ;
- rapport du nombre de coffres et d’escaliers effectivement injectés ;
- rapport de capacité et avertissements sur les données qui ne sont pas encore injectées ;
- génération d’un exécutable Windows autonome avec PyInstaller.

La deuxième étape de la feuille de route est engagée : les éléments interactifs portés par la grille sont maintenant visibles et éditables. L’édition des tables détaillées associées, comme le contenu exact des coffres, les destinations d’escaliers et les formations ennemies, reste à compléter. L’injection dans un nouveau ROM nécessite toujours une recompression sûre et un export de patch.

## Lancer depuis les sources

Prérequis : Python 3.11 ou plus récent avec Tk.

```powershell
python -m pip install -e .
python -m arcana_editor
```

L’application détecte automatiquement `Arcana (USA).sfc` dans le dossier courant. Le dump de référence possède le SHA-256 suivant :

```text
aac9d6f2b8408e4bbdc83ebbba755428caf8021fefbfac7220fb4c772abd9944
```

## Construire le `.exe`

```powershell
python -m pip install pytest pyinstaller
.\build.ps1
```

Le résultat est `dist\ArcanaMapStudio.exe`. Placez votre propre `Arcana (USA).sfc` à côté de l’exécutable ou utilisez **Fichier > Ouvrir un ROM**.

## Construire un ROM modifié

Utilisez **Fichier > Construire un ROM modifié** ou `Ctrl+B`. L’éditeur recompresse les cartes, les replace dans leur zone d’origine, met à jour les pointeurs et le checksum, puis redécompresse chaque carte du fichier produit pour vérifier l’export. Le dump source n’est jamais écrasé.

La version 0.7.1 reconstruit et relocalise entièrement les tables de coffres et d’escaliers dans les zones libres vérifiées des banques `$18` et `$03`. Elle prend en charge la création et la suppression de coffres, l’ajout d’escaliers, ainsi que la conversion d’une sortie externe en destination de donjon. Les rencontres, objets personnalisés, statistiques et inventaires de vendeurs restent sauvegardés dans le projet mais ne sont pas encore écrits dans le ROM.

## Extraire les cartes

```powershell
python -m arcana_editor.extract "Arcana (USA).sfc" extracted
```

La commande crée un manifeste JSON et 14 grilles binaires décompressées de 1 024 octets. Ces fichiers générés ne doivent pas être publiés sans vérifier vos droits.

## Tests

```powershell
python -m pytest
```

Les tests indépendants du ROM fonctionnent sur GitHub Actions. Les tests d’intégration sont automatiquement ignorés quand le ROM propriétaire est absent.

## Architecture

- `src/arcana_editor/rom.py` : en-tête SNES, adressage LoROM, décompression HAL et tables de cartes.
- `src/arcana_editor/project.py` : modèle de projet non destructif et sérialisation JSON.
- `src/arcana_editor/app.py` : interface Tkinter.
- `src/arcana_editor/extract.py` : extraction reproductible des données de cartes.
- `tests/` : tests unitaires et tests d’intégration locaux.

## Décompilation

Une désassemblage 65c816 annotée existe déjà dans le projet public `SarahShinespark/arcana-disassembly`. Elle constitue une excellente référence technique, mais aucune licence explicite n’y était affichée lors de la création de ce dépôt. Son code n’est donc pas recopié ici. Arcana Map Studio réimplémente uniquement les formats nécessaires à partir du comportement observé et des tables du ROM.

Feuille de route :

1. **partiellement livré en 0.6** — compresseur HAL, reconstruction ROM et injection des cartes ; export BPS/IPS et injection des autres bases encore à faire ;
2. **avancée en 0.7.1** — tables de coffres et d’escaliers reconstruites avec création, suppression, relocation et conversion des sorties externes ; rencontres encore à finaliser ;
3. **en cours** — aperçu des murs et couloirs en perspective livré en 0.3 ; extraction et rendu des véritables tuiles SNES encore à réaliser ;
4. **livré en 0.5 au niveau projet — Base de données d’objets** : édition et création, statistiques, prix, vendeurs et disponibilité automatique dans les coffres ; l’injection ROM attend le constructeur ;
5. édition des villes, ennemis, statistiques générales et dialogues ;
6. pipeline de reconstruction vérifiable du ROM à partir d’un dump fourni localement ;
7. **partiellement livré** — historique annuler/rétablir et outils de dessin façon RPG Maker ; calques, sélection avancée et validation restent à faire.

## Module Base de données d’objets — plan de match

Le module prend la forme d’une base de données inspirée de RPG Maker, accessible depuis la barre d’outils et organisée par catégories : objets, armes, armures, boucliers, accessoires et cartes. La version 0.5 réalise l’édition au niveau du projet ; l’écriture de ces tables dans un ROM modifié reste liée au futur constructeur.

### Édition et création

- modifier le nom, la description, la catégorie, l’identifiant et l’icône logique d’un objet existant ;
- dupliquer un objet comme point de départ ;
- créer un objet dans un emplacement ROM libre ou étendre les tables lorsque le constructeur de ROM sera disponible ;
- détecter les identifiants libres, doublons, limites de texte et références cassées ;
- conserver les créations dans le projet sans modifier le dump original ;
- rendre immédiatement tout objet existant ou créé disponible dans le sélecteur de contenu des coffres.

### Statistiques d’équipement

Pour les armes, armures, boucliers et accessoires, l’éditeur exposera les statistiques réellement prises en charge par le jeu :

- attaque, défense et défense magique ;
- bonus ou pénalités de caractéristiques identifiés dans les tables du ROM ;
- personnages ou classes autorisés à équiper l’objet ;
- effets spéciaux, résistances et propriétés maudites lorsque leur format aura été confirmé ;
- prix d’achat, valeur de revente et indicateur « non vendable » ;
- comparaison avec un autre équipement et aperçu de l’impact sur les statistiques.

### Vendeurs et disponibilité

- liste des magasins et vendeurs présents dans les villes ;
- cases à cocher pour choisir quels vendeurs proposent l’objet ;
- prix global par défaut et surcharge facultative par vendeur si le moteur du jeu le permet ;
- ordre d’affichage dans chaque boutique ;
- conditions de disponibilité liées au chapitre ou à la progression lorsqu’elles existent ;
- avertissement lorsqu’un magasin dépasse la capacité de sa table ROM.

### Intégration avec les coffres

Le catalogue des coffres utilisera une source unique partagée avec la base de données. Une création ou un renommage sera donc visible immédiatement dans l’éditeur d’événements. Les références seront stockées par catégorie et identifiant, et non uniquement par nom, pour éviter de casser les coffres lors d’un renommage.

### Étapes techniques

1. décoder les tables de prix, statistiques, restrictions d’équipement et inventaires des boutiques ;
2. étendre `GameItem` et le format de projet avec ces données sans casser les projets existants ;
3. créer l’interface Base de données avec recherche, filtres, duplication et validation ;
4. relier les vendeurs et le sélecteur de coffres au catalogue du projet ;
5. ajouter l’allocation d’identifiants et la création d’objets ;
6. injecter les tables modifiées via le futur constructeur de ROM et vérifier le résultat dans un émulateur.

## Légalité

Le ROM, les graphismes, textes, musiques et autres ressources d’Arcana appartiennent à leurs ayants droit. Ce dépôt ne doit contenir ni ROM ni contenu extrait. L’utilisateur doit fournir légalement son propre dump. Le logiciel génère des projets et, à terme, des patchs ne contenant pas le jeu complet.

## Licence

Le code original d’Arcana Map Studio est distribué sous licence MIT. Cette licence ne s’applique pas au jeu Arcana ni à ses ressources.
