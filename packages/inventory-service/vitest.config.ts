import { defineConfig } from 'vitest/config';
import { resolve } from 'path';

export default defineConfig({
  test: {
    globals: false,
    environment: 'node',
    testTimeout: 10000,
    hookTimeout: 10000,
    env: {
      DATABASE_URL: 'postgresql://copio:copio_dev@localhost:5432/copio',
    },
  },
});
