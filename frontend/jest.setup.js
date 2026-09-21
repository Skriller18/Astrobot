require("@testing-library/jest-dom");

// jsdom ships neither of these, but the SSE client decodes stream chunks with them.
const { TextDecoder, TextEncoder } = require("node:util");
global.TextDecoder ??= TextDecoder;
global.TextEncoder ??= TextEncoder;
