// The map, in E.V.'s hand.
//
// A basemap is data plus a style, and the style is the whole of the look: the
// same tiles that draw a paper-white street map draw this one. So this file
// is the aesthetic, written as rules rather than pixels -- which is also why
// no tile server has any say in it.
//
// Two decisions carry most of the appearance.
//
// The roads glow because each class is drawn twice: a wide, nearly
// transparent line underneath and a thin bright one on top. Canvas has no
// blur here, and a wide soft line under a narrow hard one is what a glow is
// made of anyway -- the same trick the ring uses, one layer down.
//
// The land is barely lighter than the page and the water is barely darker,
// so the coast reads as an edge rather than as a colour. Everything
// saturated is spent on the roads, because they are the thing being looked
// at, and a map where the parks and the sea also glow is a map with no
// subject.
//
// The schema is Protomaps basemap v4: `earth`, `water`, `landuse`,
// `buildings`, `roads`, `boundaries`, `places`. A layer this style names and
// the file does not carry simply does not draw, which is the failure anyone
// would want -- a missing class, not a missing map.

import type { StyleSpecification } from "maplibre-gl";

/// Read from the stylesheet so the map follows the accent and the theme
/// rather than carrying a second palette that drifts from the first.
function palette() {
  const style = getComputedStyle(document.documentElement);
  const read = (name: string, fallback: string) =>
    style.getPropertyValue(name).trim() || fallback;
  return {
    page: read("--page", "#0d1421"),
    neon: read("--neon", "#3fa5f6"),
    soft: read("--neon-soft", "#7db8ff"),
    ink: read("--ink", "#e6eaf2"),
  };
}

/// A colour with an alpha, from a hex the stylesheet gave us.
function fade(hex: string, alpha: number): string {
  const value = Number.parseInt(hex.replace("#", ""), 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

/// Where the tiles come from, and -- optionally -- the glyphs labels need.
export interface Ground {
  /// The pmtiles url, which is a local one: `pmtiles://` over a range reader
  /// that never leaves this machine.
  tiles: string;
  /// SDF glyph ranges. Labels need them and they are a second download, so a
  /// map without them draws its streets and skips its names rather than
  /// filling the console with failures for something nobody asked for.
  glyphs?: string;
}

/// One road class, drawn as a glow and a core.
///
/// `at` is the zoom the class appears at: motorways from far out, footpaths
/// only when the view is already a street. Widths interpolate with zoom,
/// because a road drawn at a constant pixel width is a road that swallows the
/// city as you pull back.
interface Road {
  kinds: string[];
  at: number;
  glow: [number, number];
  core: [number, number];
  bright: number;
}

const ROADS: Road[] = [
  { kinds: ["highway"], at: 5, glow: [3, 26], core: [0.9, 7], bright: 1 },
  { kinds: ["major_road"], at: 8, glow: [2.4, 18], core: [0.7, 5], bright: 0.85 },
  { kinds: ["medium_road"], at: 11, glow: [2, 12], core: [0.6, 3.4], bright: 0.62 },
  { kinds: ["minor_road"], at: 13, glow: [1.6, 8], core: [0.5, 2.2], bright: 0.44 },
];

export function hudMap({ tiles, glyphs }: Ground): StyleSpecification {
  const { page, neon, soft, ink } = palette();

  const layers: StyleSpecification["layers"] = [
    {
      id: "page",
      type: "background",
      paint: { "background-color": page },
    },
    {
      // Land, a shade off the page. Any more and the map becomes a shape on
      // a background rather than a surface with an edge.
      id: "earth",
      type: "fill",
      source: "ground",
      "source-layer": "earth",
      paint: { "fill-color": fade(soft, 0.05) },
    },
    {
      id: "green",
      type: "fill",
      source: "ground",
      "source-layer": "landuse",
      filter: ["in", ["get", "kind"], ["literal", ["park", "forest", "wood", "nature_reserve", "grass"]]],
      paint: { "fill-color": "rgba(70, 150, 110, 0.13)" },
    },
    {
      // Water goes darker, not bluer. The sea in the reference is nearly the
      // page itself, and the coastline is the only thing that says so.
      id: "water",
      type: "fill",
      source: "ground",
      "source-layer": "water",
      paint: { "fill-color": "rgba(4, 9, 18, 0.55)" },
    },
    {
      id: "coast",
      type: "line",
      source: "ground",
      "source-layer": "water",
      paint: { "line-color": fade(neon, 0.3), "line-width": 0.6 },
    },
    {
      // Buildings, only once the view is a neighbourhood. Faint: they are
      // texture, and the streets are the subject.
      id: "buildings",
      type: "fill",
      source: "ground",
      "source-layer": "buildings",
      minzoom: 14,
      paint: {
        "fill-color": fade(soft, 0.07),
        "fill-outline-color": fade(neon, 0.14),
      },
    },
  ];

  // The roads, glow beneath core, quiet classes first so the motorways end
  // up on top of everything they cross.
  for (const road of [...ROADS].reverse()) {
    const filter = ["in", ["get", "kind"], ["literal", road.kinds]] as never;
    layers.push({
      id: `${road.kinds[0]}-glow`,
      type: "line",
      source: "ground",
      "source-layer": "roads",
      filter,
      minzoom: road.at,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": fade(neon, 0.13 * road.bright),
        "line-blur": 2,
        "line-width": [
          "interpolate",
          ["exponential", 1.6],
          ["zoom"],
          road.at,
          road.glow[0],
          18,
          road.glow[1],
        ],
      },
    });
    layers.push({
      id: `${road.kinds[0]}-core`,
      type: "line",
      source: "ground",
      "source-layer": "roads",
      filter,
      minzoom: road.at,
      layout: { "line-cap": "round", "line-join": "round" },
      paint: {
        "line-color": fade(soft, 0.45 + 0.5 * road.bright),
        "line-width": [
          "interpolate",
          ["exponential", 1.6],
          ["zoom"],
          road.at,
          road.core[0],
          18,
          road.core[1],
        ],
      },
    });
  }

  layers.push({
    // Borders, dashed and dim. They are context, not content.
    id: "boundaries",
    type: "line",
    source: "ground",
    "source-layer": "boundaries",
    paint: {
      "line-color": fade(ink, 0.22),
      "line-width": 0.7,
      "line-dasharray": [3, 3],
    },
  });

  // Names, when the glyphs to draw them with are here. Without them MapLibre
  // would ask for every range and fail at every one, so the map simply keeps
  // quiet instead.
  if (glyphs) {
    layers.push({
      id: "places",
      type: "symbol",
      source: "ground",
      "source-layer": "places",
      filter: ["in", ["get", "kind"], ["literal", ["country", "region", "locality"]]],
      layout: {
        "text-field": ["get", "name"],
        "text-font": ["Noto Sans Regular"],
        "text-size": [
          "interpolate",
          ["linear"],
          ["zoom"],
          3,
          9,
          12,
          14,
        ],
        "text-letter-spacing": 0.08,
        "text-max-width": 8,
      },
      paint: {
        "text-color": ink,
        "text-halo-color": fade(page, 0.9),
        "text-halo-width": 1.4,
      },
    });
  }

  return {
    version: 8,
    ...(glyphs ? { glyphs } : {}),
    sources: {
      ground: {
        type: "vector",
        url: `pmtiles://${tiles}`,
      },
    },
    layers,
  } as StyleSpecification;
}
