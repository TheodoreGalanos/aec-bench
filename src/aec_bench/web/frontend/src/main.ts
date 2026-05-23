// ABOUTME: Entry point for the Svelte SPA.
// ABOUTME: Mounts the root App component into the #app div.

import App from "./App.svelte";
import { mount } from "svelte";

const app = mount(App, { target: document.getElementById("app")! });

export default app;
