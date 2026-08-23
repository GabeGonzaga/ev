<script setup lang="ts">
// The map: streets, drawn here, from a file that lives on this machine.
//
// A map is normally the most talkative thing an application does -- every pan
// and every zoom is a request, and the shape of those requests is a record of
// where somebody was looking. This one asks nothing of anybody. The basemap
// is a single PMTiles archive beside the journal, addressed by byte range, so
// the renderer reads the few kilobytes under the view through the same door
// every other reading goes through and no tile host is ever told anything.
//
// What that costs, said plainly: the file has to be got once and it is large,
// and search and driving distances are not here, because both of those are
// services rather than data. What it buys is a map that works with the
// aeroplane mode on and looks like the rest of the display, because the style
// is ours (see `mapStyle.ts`) rather than a vendor's.

import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from "vue";
import * as api from "../../api";
import { t } from "../../i18n";
import { hudMap } from "./mapStyle";
import HudPane from "./HudPane.vue";

const emit = defineEmits<{ close: [] }>();

const holder = ref<HTMLDivElement | null>(null);
/// Shallow: MapLibre's Map is a large object with its own internal graph, and
/// making it deeply reactive would have Vue walk it on every frame.
const map = shallowRef<unknown>(null);

const pending = ref(true);
const missing = ref(false);
const trouble = ref<string | null>(null);

/// Where the view starts. Nowhere in particular and far enough out that any
/// file, whatever it covers, has something under the camera.
const START = { lon: -9.14, lat: 38.72, zoom: 5 };

async function draw() {
  try {
    if (!(await api.mapPresent())) {
      missing.value = true;
      return;
    }

    // The pane draws its own waiting line instead of its slot, so the element
    // the renderer needs does not exist until this says so -- and asking for
    // it any earlier is how this first deadlocked, waiting forever for a
    // container that was waiting for it.
    pending.value = false;
    await nextTick();
    const box = holder.value;
    if (!box) return;

    const [{ Map, addProtocol }, { PMTiles, Protocol }] = await Promise.all([
      import("maplibre-gl"),
      import("pmtiles"),
    ]);

    // The reader. PMTiles asks for ranges and does not care where they come
    // from, which is the whole reason a local file works without a server.
    const source = {
      getKey: () => "basemap",
      getBytes: async (offset: number, length: number) => ({
        data: await api.mapRange(offset, length),
      }),
    };

    const protocol = new Protocol();
    protocol.add(new PMTiles(source as never));
    addProtocol("pmtiles", protocol.tile);

    map.value = new Map({
      container: box,
      style: hudMap({ tiles: "basemap" }),
      center: [START.lon, START.lat],
      zoom: START.zoom,
      // Nothing is fetched from anywhere, so there is nothing to attribute to
      // a host -- but the data is OpenStreetMap's and saying so is the
      // licence, not a courtesy.
      attributionControl: { compact: true, customAttribution: "© OpenStreetMap" },
    });
  } catch (error) {
    trouble.value = String(error);
  } finally {
    pending.value = false;
  }
}

onMounted(draw);

onBeforeUnmount(() => {
  // The renderer holds a WebGL context, and a display that opens and closes
  // this window all day would collect them until the browser started
  // dropping the oldest.
  (map.value as { remove?: () => void } | null)?.remove?.();
  map.value = null;
});
</script>

<template>
  <HudPane
    name="map"
    :pending="pending"
    :error="trouble"
    :waiting="t('map.waiting')"
    :at="{ x: 60, y: 90, width: 620, height: 420 }"
    @close="emit('close')"
  >
    <!-- The empty state is the useful one here: a map with no file is not
         broken, it is a map nobody has given the ground to yet, and the way
         out is a path and a place to get it. -->
    <div v-if="missing" class="absent">
      <p class="says">&gt; {{ t("map.absent") }}</p>
      <p class="where">{{ t("map.put_it") }}</p>
      <code>~/Library/Application Support/EV/maps/basemap.pmtiles</code>
      <p class="note">{{ t("map.get_one") }}</p>
    </div>

    <div v-else ref="holder" class="ground" />
  </HudPane>
</template>

<style scoped>
.ground {
  flex: 1;
  min-height: 0;
  border: 1px solid var(--panel-border);
  border-radius: 2px;
  overflow: hidden;
}

/* MapLibre paints its own background and draws its own attribution; both are
   made to sit inside the panel rather than on top of it. */
.ground :deep(.maplibregl-ctrl-attrib) {
  background: rgba(13, 20, 33, 0.72);
  color: var(--text-dim);
  font-family: var(--mono);
  font-size: var(--telemetry);
}

.ground :deep(.maplibregl-ctrl-attrib a) {
  color: var(--text-dim);
}

.absent {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 2px;
  font-size: var(--body);
}

.says {
  margin: 0;
  font-family: var(--mono);
  color: var(--muted);
}

.where,
.note {
  margin: 0;
  color: var(--text-dim);
  font-size: var(--telemetry);
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

code {
  font-family: var(--mono);
  font-size: 11px;
  color: var(--ink);
  padding: 6px 8px;
  border: 1px solid var(--panel-border);
  border-radius: 2px;
  background: rgba(63, 165, 246, 0.06);
  user-select: all;
  word-break: break-all;
}
</style>
