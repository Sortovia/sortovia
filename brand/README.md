# Sortovia logo kit (design 6e)

Vector-first logo files for Sortovia. Every SVG has its lettering converted to
shapes, so it needs no fonts installed and scales cleanly from a 16 px icon up
to a billboard. Edit or resize the SVGs; the PNGs are ready-made exports.

## Folders

| Folder | What's in it |
|---|---|
| `svg/` | Master vector files (use these first) |
| `svg/uwp/` | Vector sources for the Xbox/UWP tile assets |
| `png/icon/` | App icon at 16, 24, 32, 44, 48, 64, 128, 256, 512, 1024 px |
| `png/` | Large PNGs (1200 px wide) of each logo layout |
| `uwp-assets/` | Drop-in images for a UWP / Xbox app's `Assets` folder |
| `licenses/` | SIL Open Font License for the two fonts used |

## Main files

- `svg/sortovia-icon.svg`: the outlined square app icon (use this for icons).
- `svg/sortovia-mark.svg`: the S path, folder, play button and film with no square.
- `svg/sortovia-wordmark.svg`: "sortovia" on its own, in teal.
- `svg/sortovia-logo-stacked-dark.svg`: icon, name and tagline on the navy background.
- `svg/sortovia-logo-stacked-transparent.svg`: same, with no background.
- `svg/sortovia-logo-notagline.svg`: icon and name, with no tagline.
- `svg/sortovia-logo-horizontal.svg`: icon beside the name, for headers and banners.

## UWP / Xbox assets (`uwp-assets/`)

File names match the Visual Studio UWP template, so they can replace the
placeholder images in the project's `Assets` folder directly:
`Square44x44Logo.png`, `Square150x150Logo.png`, `Wide310x150Logo.png`,
`SmallTile.png` (71×71), `LargeTile.png` (310×310), `StoreLogo.png` (50×50),
`SplashScreen.png` (620×300). The splash and tile backgrounds are `#0F1A24`.

## Brand values

| Use | Value |
|---|---|
| Teal (path, outline, name) | `#2EC4B6` |
| Icon square fill | `#16283A` |
| Background navy | `#0F1A24` |
| Tagline grey | `#A9BAC0` |
| Icons | `#FFFFFF` |
| Name font | Righteous (Google Fonts, OFL) |
| Tagline font | Outfit Light 300 (Google Fonts, OFL) |
| Tagline | "Your library, on the right path." |

Rounded square: 260×260 with 55 px corner radius and a 6 px teal outline.
