import { createPinia } from "pinia";
import { createApp } from "vue";
import App from "./App.vue";
import { inApp } from "./api";
import "./style.css";

// The one thing the stylesheet needs to know about which shell it is in: the
// app's window is transparent and macOS draws the material behind it, a
// browser tab has nothing behind it and paints its own background.
document.documentElement.classList.add(inApp ? "in-app" : "in-browser");

createApp(App).use(createPinia()).mount("#app");
