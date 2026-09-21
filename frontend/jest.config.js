const nextJest = require("next/jest");
module.exports = nextJest({ dir: "./" })({
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.js"],
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" },
});
