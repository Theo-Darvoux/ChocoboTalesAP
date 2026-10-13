# Guide de configuration de Chocobo Tales

Ce guide va de l'installation de l'apworld jusqu'à une partie multimonde.

## Logiciels requis

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.6.7 ou plus récent
- [BizHawk](https://tasvideos.org/BizHawk/ReleaseHistory) 2.10 ou plus récent (son cœur NDS est melonDS)
  - Windows : lancez d'abord l'installeur des prérequis de BizHawk.
  - Linux : BizHawk a besoin de Mono ; lancez-le avec `EmuHawkMono.sh`.
- L'apworld de Chocobo Tales : `chocobo_tales.apworld`, dans la
  [dernière release](https://github.com/Theo-Darvoux/ChocoboTalesAP/releases/latest)
- Une ROM de Final Fantasy Fables: Chocobo Tales, version **européenne** (code de jeu `AEHP`,
  MD5 `a392490af90e31f2ce68d18b11833080`). Vous devez la dumper vous-même ; elle n'est pas fournie.

## Logiciels optionnels

- [Universal Tracker](https://github.com/FarisTheAncient/Archipelago/releases), qui fonctionne avec ce monde sans
  fichier YAML.

## Installer l'apworld

1. Téléchargez `chocobo_tales.apworld` depuis la dernière release.
2. Double-cliquez dessus, ou ouvrez l'Archipelago Launcher, cliquez sur **Install APWorld** et choisissez le
   fichier. Dans les deux cas, il est copié dans le dossier `custom_worlds` de votre installation d'Archipelago.
3. Redémarrez le Launcher. « Chocobo Tales » apparaît alors dans la liste des jeux.

Pour mettre à jour, installez le nouveau `.apworld` de la même façon : il remplace l'ancien. Tous ceux qui
génèrent ou jouent une seed doivent utiliser la même version de l'apworld.

## Créer votre fichier d'options (YAML)

Le fichier YAML contient votre nom de slot et les options de votre monde. Au choix :

- **Les presets de la release** (recommandé) : téléchargez un des presets et modifiez-le dans un éditeur de texte.
  - `chocobo_tales.yaml` : l'expérience complète, chaque carte est un objet à part.
  - `chocobo_tales_compact.yaml` : des paquets de cartes par monstre et moins de checks, pour une partie plus
    courte.
  - `chocobo_tales_epilogues.yaml` : mélange aussi les épilogues des livres.
- **Options Creator** : dans le Launcher, ouvrez **Options Creator**, choisissez Chocobo Tales et exportez un YAML.
- **Modèle** : dans le Launcher, cliquez sur **Generate Template Options**. Cela écrit `Chocobo Tales.yaml`, avec
  toutes les options et leur description, dans le dossier `Players/Templates`.

Mettez ensuite votre nom de slot dans `name:`. Les noms doivent être uniques dans un multimonde ; les presets
utilisent `Player{number}`, qu'Archipelago transforme en Player1, Player2, ...

Chaque option est décrite sur la
[page du jeu](https://github.com/Theo-Darvoux/ChocoboTalesAP/blob/main/chocobo_tales/docs/en_Chocobo%20Tales.md)
(en anglais) et dans les commentaires des fichiers YAML.

## Générer une partie

La génération doit se faire sur un ordinateur où l'apworld de Chocobo Tales est installé : archipelago.gg ne
connaît pas ce jeu.

1. Rassemblez les fichiers YAML de tous les joueurs dans le dossier `Players` de votre installation d'Archipelago
   (rien d'autre à part le dossier `Templates`).
2. Dans le Launcher, cliquez sur **Generate**. Le résultat est un `.zip` dans le dossier `output`.
3. Dans ce zip, chaque joueur de Chocobo Tales a un fichier de patch `.apcts` : envoyez à chacun le sien.

## Héberger la partie

- **Sur archipelago.gg** : ouvrez [la page d'upload](https://archipelago.gg/uploads), envoyez le `.zip` et créez une
  room. Le site n'a pas besoin de l'apworld pour héberger une partie générée ailleurs.
- **En local** : dans le Launcher, cliquez sur **Host** et choisissez le `.zip`. Les autres joueurs ont besoin de
  votre adresse et du port (38281 par défaut) pour se connecter.

## Configurer Archipelago pour Chocobo Tales

À faire une seule fois. Vous pouvez modifier `host.yaml` (dans le dossier d'Archipelago) vous-même, ou laisser
Archipelago vous le demander :

1. `chocobo_tales_options: rom_file` : le chemin de votre ROM de Chocobo Tales. S'il n'est pas défini, Archipelago
   demande la ROM la première fois que vous ouvrez un patch, puis s'en souvient.
2. `bizhawkclient_options: emuhawk_path` : le chemin de `EmuHawk.exe` (Windows) ou de `EmuHawkMono.sh` (Linux).
   C'est optionnel : avec lui, le client lance BizHawk avec le jeu et le script de connexion.

## Jouer

1. Dans le Launcher, cliquez sur **Open Patch** et choisissez votre fichier `.apcts` (ou double-cliquez dessus).
   Archipelago construit le jeu patché à côté, un fichier `.nds` du même nom, et ouvre le **BizHawk Client**.
2. Si `emuhawk_path` est défini, BizHawk démarre avec le jeu et le script de connexion. Sinon :
   1. Ouvrez le `.nds` patché dans BizHawk (**File > Open ROM**).
   2. Ouvrez **Tools > Lua Console**, puis **Script > Open Script...**, et chargez
      `connector_bizhawk_generic.lua` depuis le dossier `data/lua` de votre installation d'Archipelago.
3. Dans le BizHawk Client, entrez l'adresse du serveur en haut (par exemple `archipelago.gg:38281`) et cliquez sur
   **Connect**. Votre nom de slot est lu dans la ROM ; entrez le mot de passe de la room s'il y en a un.
4. Commencez une **nouvelle partie** dans Chocobo Tales et jouez. Les checks sont envoyés dès que vous les
   réussissez, et les objets reçus arrivent directement dans votre sauvegarde (cartes dans la collection,
   chocobos, modes des livres).

Le client affiche « Detected Chocobo Tales (...), Archipelago version » quand BizHawk et le client communiquent.

### Bon à savoir

- Jouez toujours avec le `.nds` patché. Le client refuse la ROM d'origine, qui donnerait elle-même les objets
  d'Archipelago.
- Gardez BizHawk à vitesse normale (**Config > Speed/Skip**). En accéléré, BizHawk peut arrêter d'exécuter le script
  de connexion, et le client perd alors la connexion.
- BizHawk nomme la sauvegarde d'après le fichier ROM : chaque seed a donc sa propre sauvegarde. Gardez le `.nds`
  patché et sa sauvegarde jusqu'à la fin du multimonde.
- Les messages de récompense du jeu donnent le nom de l'objet trouvé (« Objet trouvé : ... »), dans toutes les
  langues. Un message disant qu'il n'y a rien à obtenir signifie que ce check est désactivé dans vos options.
- Chaque duel après le tutoriel demande un deck de 15 cartes. Gardez `starting_cards` à 15 ou plus, sauf si vous
  voulez passer le premier chapitre à chercher des cartes.

## Dépannage

- **« Chocobo Tales » n'apparaît pas dans le Launcher ou l'Options Creator** : l'apworld n'est pas installé, ou il
  l'est en double. Cherchez d'anciennes copies dans `custom_worlds` (et `lib/worlds`), gardez un seul
  `chocobo_tales.apworld`, puis redémarrez le Launcher.
- **La ROM est refusée à l'ouverture du patch** : seule la ROM européenne avec le MD5 ci-dessus est prise en
  charge. Vérifiez que ce n'est pas un dump tronqué, patché ou d'une autre région.
- **Le client ne voit pas BizHawk** : vérifiez que le script Lua de connexion tourne dans la Lua Console, et qu'un
  seul BizHawk Client est ouvert.
- **Le client se déconnecte au bout d'un moment** : remettez BizHawk à 100 % et rechargez le script de connexion.
- **Autre chose** : ouvrez une issue sur le
  [dépôt GitHub](https://github.com/Theo-Darvoux/ChocoboTalesAP/issues) avec votre version de l'apworld, votre YAML
  et le log du client (dans le dossier `logs` d'Archipelago).
