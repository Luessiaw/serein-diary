/*
 * P2 静态样本。`data` 对应 docs/plan-v1.1.md 定义的可迁移条目文件：
 * metadata.json、content.md、comments.json 与 media-manifest.json；`ui`
 * 则刻意与数据契约分离。
 *
 * 最后一项仅是浏览器内草稿。其 ID 和时间戳为 null 是有意设计：真实
 * 服务会在持久化条目前生成这些字段。
 */
window.SereinMockEntries = [
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "4ba4c93a-6068-4e0f-9a70-145c1e88f01a",
        date: "2026-06-25",
        timezone: "Asia/Shanghai",
        created_at: "2026-06-25T08:12:00+08:00",
        updated_at: "2026-06-25T08:12:00+08:00",
        revision: 1,
        title: "雨季的早晨",
      },
      content: "醒来时窗外没有雨，只有潮湿的树叶。\n\n泡一杯茶，再慢慢开始今天。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "84a0f50c-729b-4e63-b3c2-99b937f7f5c1",
        date: "2026-06-24",
        timezone: "Asia/Shanghai",
        created_at: "2026-06-24T08:30:00+08:00",
        updated_at: "2026-06-24T21:12:00+08:00",
        revision: 2,
      },
      content: "雨停以后，窗边留下很淡的光。\n\n一些尚未整理的句子，慢慢向下延伸。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "editing" },
    data: {
      metadata: {
        schema_version: 1,
        id: "d2644aa2-5724-4f8c-b411-e9b34de5372a",
        date: "2026-05-31",
        timezone: "Asia/Shanghai",
        created_at: "2026-05-31T18:44:00+08:00",
        updated_at: "2026-05-31T19:18:00+08:00",
        revision: 3,
        title: "五月末",
        location: "家",
      },
      content: "今天的风很轻。\n这里保留为正在编辑的静态样本。",
      comments: {
        schema_version: 1,
        comments: [
          {
            id: "dd2d3ba6-3d96-4975-a66c-6d5f33977a04",
            body: "以后再想想这里。",
            created_at: "2026-05-31T19:15:00+08:00",
            updated_at: "2026-05-31T19:15:00+08:00",
            anchor: null,
          },
        ],
      },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "8d48fcd0-10d4-4b2c-8829-5a660d7feeb3",
        date: "2026-06-24",
        timezone: "Asia/Shanghai",
        created_at: "2026-06-24T19:10:00+08:00",
        updated_at: "2026-06-24T19:10:00+08:00",
        revision: 1,
      },
      content: "傍晚又下了一阵雨。\n\n路灯亮起来以后，空气才真正凉下来。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "3a4822f7-6694-490c-87d1-5bb086aa0d3d",
        date: "2026-04-12",
        timezone: "Asia/Shanghai",
        created_at: "2026-04-12T14:10:00+08:00",
        updated_at: "2026-04-12T14:10:00+08:00",
        revision: 1,
      },
      content: "午后去了一趟很久没有去的街角。\n\n店铺换了招牌，光线还是旧的。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "2e59fd4c-808e-4eb6-8b7d-61382ebbd134",
        date: "2025-12-31",
        timezone: "Asia/Shanghai",
        created_at: "2025-12-31T23:36:00+08:00",
        updated_at: "2025-12-31T23:36:00+08:00",
        revision: 1,
        title: "年末的灯",
      },
      content: "跨年的声音从远处传来。\n\n我没有许愿，只把桌面收拾干净。",
      comments: {
        schema_version: 1,
        comments: [
          {
            id: "86fc08e6-87c6-4d3c-b376-e02177aa2384",
            body: "这一句值得留着。",
            created_at: "2026-01-02T09:10:00+08:00",
            updated_at: "2026-01-02T09:10:00+08:00",
            anchor: {
              quote: "只把桌面收拾干净",
              prefix: "我没有许愿，",
              suffix: "。",
            },
          },
        ],
      },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "489f5214-d440-4c80-ba2f-43cb3f09e2e3",
        date: "2025-10-03",
        timezone: "Asia/Shanghai",
        created_at: "2025-10-03T16:22:00+08:00",
        updated_at: "2025-10-03T16:22:00+08:00",
        revision: 1,
      },
      content: "下午的云像一层很慢的海。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "5a06c24b-6f57-44f9-9fd1-a80b30a23675",
        date: "2025-07-18",
        timezone: "Asia/Shanghai",
        created_at: "2025-07-18T20:08:00+08:00",
        updated_at: "2025-07-18T20:08:00+08:00",
        revision: 1,
        title: "夏夜散步",
        location: "河边",
      },
      content: "蝉声在树顶，河面比白天安静。\n\n走回家时，鞋底沾了一点草。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "a80b3415-5518-4edc-b5a4-6d3ebf7bb2e7",
        date: "2025-03-02",
        timezone: "Asia/Shanghai",
        created_at: "2025-03-02T10:40:00+08:00",
        updated_at: "2025-03-02T10:40:00+08:00",
        revision: 1,
      },
      content: "把冬天的被子晒了一上午。\n\n太阳落下后，房间里仍有一点温暖。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "c5e5e2d4-619b-4f9d-a2b2-401dcab74d80",
        date: "2024-11-09",
        timezone: "Asia/Shanghai",
        created_at: "2024-11-09T17:50:00+08:00",
        updated_at: "2024-11-10T08:25:00+08:00",
        revision: 2,
        title: "傍晚的站台",
      },
      content: "列车晚了一会儿。\n\n站台上的人都在看自己的方向。",
      comments: {
        schema_version: 1,
        comments: [
          {
            id: "7be6c1a1-8e22-4bd1-9999-35a48d588c9a",
            body: "可以把这里展开写。",
            created_at: "2024-11-10T08:25:00+08:00",
            updated_at: "2024-11-10T08:25:00+08:00",
            anchor: null,
          },
        ],
      },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "f02520d4-8940-4b89-8233-a2766b8c7e22",
        date: "2024-08-16",
        timezone: "Asia/Shanghai",
        created_at: "2024-08-16T12:05:00+08:00",
        updated_at: "2024-08-16T12:05:00+08:00",
        revision: 1,
      },
      content: "一场短雨把午饭后的热气压低了。\n\n窗台上的薄荷终于直起身来。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "eaef32f0-4f84-4bb5-ae0b-58ac48b16945",
        date: "2024-02-29",
        timezone: "Asia/Shanghai",
        created_at: "2024-02-29T22:01:00+08:00",
        updated_at: "2024-02-29T22:01:00+08:00",
        revision: 1,
        title: "多出来的一天",
      },
      content: "日历给了一个小小的额外房间。\n\n没有做特别的事，也很好。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "d0bc9ce1-4b46-4e08-8d94-72567ac16ad7",
        date: "2023-12-25",
        timezone: "Asia/Shanghai",
        created_at: "2023-12-25T21:34:00+08:00",
        updated_at: "2023-12-25T21:34:00+08:00",
        revision: 1,
      },
      content: "街上的灯比平时亮一些。\n\n回家的路上买了一块面包。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "153b66d2-f47e-4ad2-bb78-d4907919e892",
        date: "2023-07-04",
        timezone: "Asia/Shanghai",
        created_at: "2023-07-04T19:48:00+08:00",
        updated_at: "2023-07-04T19:48:00+08:00",
        revision: 1,
        title: "夏天的雷声",
      },
      content: "雷声滚过屋顶时，猫钻进了椅子下面。\n\n雨没有下很久。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "reading" },
    data: {
      metadata: {
        schema_version: 1,
        id: "6bf9729f-4a73-4e03-9e88-925c0fb21314",
        date: "2023-01-01",
        timezone: "Asia/Shanghai",
        created_at: "2023-01-01T00:20:00+08:00",
        updated_at: "2023-01-01T00:20:00+08:00",
        revision: 1,
      },
      content: "新年的第一分钟很安静。",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
  {
    ui: { mode: "new" },
    data: {
      metadata: {
        schema_version: 1,
        id: null,
        date: null,
        timezone: "Asia/Shanghai",
        created_at: null,
        updated_at: null,
        revision: null,
      },
      content: "",
      comments: { schema_version: 1, comments: [] },
      mediaManifest: { schema_version: 1, media: [] },
    },
  },
];
