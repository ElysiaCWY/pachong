# 人社与行业情报自动抓取项目

本项目用于每日自动抓取人力新闻与政策动态，结合 AI 完成高价值筛选、摘要生成与趋势洞察，并通过钉钉机器人发送汇总简报。

## 功能特性

1.  **人力新闻抓取（企业/行业）**：
    *   三茅日报、新浪财经、第一资源、第一财经大政、中国劳动保障新闻网人力资源板块。
    *   HRbrand 品牌动态（近 24 小时）。
    *   HR 价值网快讯（近 24 小时，按页面时间精度过滤）。
    *   中国金融信息网独家新闻（近 24 小时）。
    *   钛媒体最新资讯（近 24 小时，Playwright 深度抓取）。
    *   界面新闻商业板块（已过滤视频）。
    *   同花顺非上市公司资讯。
    *   财富中文网商业新闻。
    *   财新网公司频道公司新闻。
    *   国家税务总局。
    *   **动脉网**：指定栏目文章（近 24 小时）。
    *   **快消品网**：多板块整合（独家、饮品、食品、日化、零售、电商、综合）。
    *   **盖世汽车**：产业与车企新闻（近 24 小时）。
    *   **InfoQ**：产业新闻板块（Playwright 深度抓取）。
    *   **创业邦 (Cyzone)**：资讯频道（Playwright 深度抓取）。
    *   **虎嗅 (Huxiu)**：资讯列表（支持相对时间解析）。
2.  **政策与动态抓取**：
    *   人社部（MOHRSS）动态与政策。
    *   国家税务总局政策法规。
    *   HR 价值网政策板块。
    *   中国政府网最新政策。
3.  **地方人社局政策抓取**：
    *   **北京**：北京市人社局政策文件。
    *   **天津**：天津市人社局政策解读。
    *   **河北**：河北省人社厅政策解读。
    *   **山西**：山西省人社厅部门文件。
    *   **内蒙古**：内蒙古人社厅政策解读。
    *   **吉林**：吉林省人社厅地方法规政策。
    *   **黑龙江**：黑龙江省人社厅政策板块（行政规范性文件、其它文件，近24小时）。
    *   **辽宁**：辽宁省人社厅政策文件三栏（辽人社规、辽人社发、辽人社，近24小时）。
4.  **AI 分析能力**：
    *   AI 批量筛选：按“对中国人力资源外包/用工市场影响”筛出高价值条目。
    *   AI 摘要生成：为入选新闻生成简洁摘要。
    *   AI 洞察分析：基于当日结果与近 3 个月历史记录，进行关联分组、当下市场分析与趋势预测。
5.  **自动推送**：
    *   支持钉钉群机器人 Webhook 推送。
    *   生成 Markdown 格式的日报，包含文章标题、链接和来源。

## 运行方式

### 1. 主程序运行（推荐）

运行主程序将执行所有已启用的抓取任务（人力新闻 + 政策动态 + 地方政策），并汇总发送一条消息。

```bash
python mohrss_local_news.py
```

### 2. 单独运行地方抓取任务

如果只想单独测试或抓取某个地方的政策，可以运行对应的脚本：

*   **北京**：`python beijing_rsj_task.py`
*   **天津**：`python tianjin_hrss_task.py`
*   **河北**：`python hebei_rst_task.py`
*   **山西**：`python shanxi_rst_task.py`
*   **内蒙古**：`python neimenggu_rst_task.py`

### 3. 单独测试某个站点抓取（示例）

```bash
python -c "from news_crawlers.hrbrand_news import crawl_hrbrand_news; print(crawl_hrbrand_news())"
python -c "from news_crawlers.hrvalue_kuai import crawl_hrvalue_kuai; print(crawl_hrvalue_kuai())"
python -c "from news_crawlers.hrvalue_policy import crawl_hrvalue_policy; print(crawl_hrvalue_policy())"
```

## 环境变量配置

请在运行前确保设置了以下环境变量（或在代码中硬编码）：

*   `DASHSCOPE_API_KEY`: 阿里云 DashScope API Key（用于 AI 筛选）。
*   `DINGTALK_GROUP1_WEBHOOK` / `DINGTALK_GROUP1_SECRET`: 钉钉群 1 的 Webhook 和 Secret。
*   `DINGTALK_GROUP2_WEBHOOK` / `DINGTALK_GROUP2_SECRET`: 钉钉群 2 的 Webhook 和 Secret。
*   兼容旧变量名：`SHIYANQUNWEBHOOK` / `SHIYANQUNSECRET`、`DINGDINGSHANGYEWEBHOOK` / `DINGDINGSHANGYESECRET`。
*   `RUN_CHINATAX`: 是否运行税务总局抓取（1=运行，0=不运行）。
*   `RUN_TOPHR`: 是否运行第一资源抓取（1=运行，0=不运行）。
*   `RUN_YICAI_HONGGUAN`: 是否运行第一财经大政抓取（1=运行，0=不运行）。
*   `RUN_CLSSN_RLZY`: 是否运行中国劳动保障新闻网人力资源抓取（1=运行，0=不运行）。
*   `RUN_HRBRAND_NEWS`: 是否运行 HRbrand 品牌动态抓取（1=运行，0=不运行）。
*   `RUN_HRVALUE_KUAI`: 是否运行 HR 价值网快讯抓取（1=运行，0=不运行）。
*   `RUN_HRVALUE_POLICY`: 是否运行 HR 价值网政策抓取（1=运行，0=不运行）。
*   `RUN_GOVCN_POLICY`: 是否运行中国政府网最新政策抓取（1=运行，0=不运行）。
*   `RUN_JIEMIAN_BUSINESS`: 是否运行界面新闻商业抓取（1=运行，0=不运行）。
*   `RUN_CNFIN_DJ`: 是否运行中国金融信息网独家抓取（1=运行，0=不运行）。
*   `RUN_TMTPOST`: 是否运行钛媒体最新抓取（1=运行，0=不运行）。
*   `RUN_VBDATA`: 是否运行动脉网抓取（1=运行，0=不运行）。
*   `RUN_FMCG_CHINA`: 是否运行快消品网抓取（1=运行，0=不运行）。
*   `RUN_GASGOO`: 是否运行盖世汽车抓取（1=运行，0=不运行）。
*   `RUN_INFOQ`: 是否运行 InfoQ 抓取（1=运行，0=不运行）。
*   `RUN_CYZONE`: 是否运行创业邦 (Cyzone) 抓取（1=运行，0=不运行）。
*   `RUN_HUXIU`: 是否运行虎嗅 (Huxiu) 抓取（1=运行，0=不运行）。
*   `RUN_HEILONGJIANG_HRSS_POLICY`: 是否运行黑龙江省人社厅政策抓取（1=运行，0=不运行）。
*   `RUN_LIAONING_HRSS_POLICY`: 是否运行辽宁省人社厅政策抓取（1=运行，0=不运行）。

常用可选参数：

*   `SINA_TARGET_DATE`: 指定新浪/第一资源目标日期（格式 `YYYY-MM-DD`）。
*   `HRVALUE_POLICY_TARGET_DATE`: 指定 HR 价值网政策目标日期（格式 `YYYY-MM-DD`）。
*   `GOVCN_POLICY_TARGET_DATE`: 指定中国政府网政策目标日期（格式 `YYYY-MM-DD`）。
*   `OUT_FILE`: 输出 Markdown 文件名（默认 `daily_all.md`）。
*   `INSIGHT_HISTORY_FILE`: 洞察历史样本文件（默认 `insight_history.jsonl`）。

## 核心文件结构

*   `mohrss_local_news.py`: 主入口脚本。
*   `news_crawlers/`: 爬虫模块目录。
    *   `beijing_rsj.py`: 北京爬虫。
    *   `tianjin_hrss.py`: 天津爬虫。
    *   `hebei_rst.py`: 河北爬虫。
    *   `shanxi_rst.py`: 山西爬虫。
    *   `neimenggu_rst.py`: 内蒙古爬虫。
    *   `jilin_hrss.py`: 吉林省人社厅地方法规政策爬虫。
    *   `heilongjiang_hrss.py`: 黑龙江省人社厅政策爬虫（行政规范性文件、其它文件，近24小时）。
    *   `liaoning_hrss.py`: 辽宁省人社厅政策文件爬虫（三栏近24小时）。
    *   `yicai_hongguan.py`: 第一财经大政爬虫。
    *   `clssn_rlzy.py`: 中国劳动保障新闻网人力资源爬虫（近 24 小时）。
    *   `hrbrand_news.py`: HRbrand 品牌动态爬虫（近 24 小时）。
    *   `cnfin_dj.py`: 中国金融信息网独家爬虫。
    *   `tmtpost.py`: 钛媒体最新爬虫（Playwright 实现）。
    *   `jiemian_business.py`: 界面新闻商业爬虫（含视频过滤）。
    *   `hrvalue_kuai.py`: HR 价值网快讯爬虫（近 24 小时）。
    *   `hrvalue_policy.py`: HR 价值网政策爬虫。
    *   `govcn_policy.py`: 中国政府网最新政策爬虫。
    *   `vbdata.py`: 动脉网爬虫（指定栏目）。
    *   `fmcg_china.py`: 快消品网爬虫（多板块）。
    *   `gasgoo.py`: 盖世汽车爬虫（产业+车企）。
    *   `infoq.py`: InfoQ 产业新闻爬虫（Playwright 实现）。
    *   `ai_crawler.py`: AI 筛选逻辑。
    *   `dingtalk.py`: 钉钉发送逻辑。
    *   ... 其他爬虫模块。

## 注意事项

*   **抓取时间**：程序会自动判断目标日期。
    *   周一：抓取上周五的数据。
    *   周二至周五：抓取昨天的数据。
    *   周末：默认不运行抓取。
*   **24 小时源说明**：
    *   HRbrand、CLSSN、HR 价值网快讯按“近 24 小时”策略抓取。
    *   部分站点时间粒度仅到“日期”，会按页面可用时间精度做近似过滤。
*   **网络环境**：部分政府网站响应较慢，脚本设置了超时处理，请保持网络畅通。
