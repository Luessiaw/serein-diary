/*
 * Static P2 samples. `data` mirrors the portable entry files described in
 * docs/plan-v1.1.md: metadata.json, content.md, comments.json, and
 * media-manifest.json. `ui` is deliberately separate from that contract.
 *
 * The final item is an in-browser draft only. Its null ID and timestamps are
 * intentional: a real server creates those values before persisting an entry.
 */
window.SereinMockEntries = [
  {
    ui: { mode: "reading", placeholderHeight: "14rem" },
    data: {
      metadata: {
        schema_version: 1,
        id: "84a0f50c-729b-4e63-b3c2-99b937f7f5c1",
        date: "2026-06-24",
        timezone: "Asia/Shanghai",
        created_at: "2026-06-24T08:30:00+08:00",
        updated_at: "2026-06-24T21:12:00+08:00",
        revision: 2,
        title: null,
        tags: ["日常"],
        mood: "平静",
        weather: "雨后",
        location: null,
        time_range: null,
        is_favorite: false,
        custom_fields: {},
      },
      content: "雨停以后，窗边留下很淡的光。\n\n一些尚未整理的句子，慢慢向下延伸。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "editing", placeholderHeight: "19rem" },
    data: {
      metadata: {
        schema_version: 1,
        id: "ec77f0b9-4970-4e4d-a822-6fa7c11f6c6e",
        date: "2026-06-23",
        timezone: "Asia/Shanghai",
        created_at: "2026-06-23T19:05:00+08:00",
        updated_at: "2026-06-23T19:18:00+08:00",
        revision: 1,
        title: null,
        tags: [],
        mood: null,
        weather: null,
        location: "家",
        time_range: null,
        is_favorite: false,
        custom_fields: {},
      },
      content: "今天的风很轻。\n这里保留为正在编辑的静态样本。",
      comments: {
        schema_version: 1,
        comments: [
          {
            id: "dd2d3ba6-3d96-4975-a66c-6d5f33977a04",
            body: "以后再想想这里。",
            created_at: "2026-06-23T19:15:00+08:00",
            updated_at: "2026-06-23T19:15:00+08:00",
            anchor: null,
          },
        ],
      },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "new", placeholderHeight: "12rem" },
    data: {
      metadata: {
        schema_version: 1,
        id: null,
        date: null,
        timezone: "Asia/Shanghai",
        created_at: null,
        updated_at: null,
        revision: null,
        title: null,
        tags: [],
        mood: null,
        weather: null,
        location: null,
        time_range: null,
        is_favorite: false,
        custom_fields: {},
      },
      content: "",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
];
