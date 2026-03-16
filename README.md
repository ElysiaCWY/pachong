# 人社与财经新闻自动抓取项目

本项目旨在每日自动抓取主要的人力资源社会保障部动态、地方人社局政策、税务总局政策以及财经新闻，并通过钉钉机器人发送汇总简报。

## 功能特性

1.  **财经新闻抓取**：
    *   整合三茅网、新浪财经、第一资源等渠道。
    *   使用 AI (通义千问) 智能筛选高价值信息（需配置 API Key）。
2.  **国家政策抓取**：
    *   人社部（MOHRSS）动态与政策。
    *   国家税务总局政策法规。
3.  **地方人社局政策抓取**（新增）：
    *   **北京**：北京市人社局政策文件。
    *   **天津**：天津市人社局政策解读。
    *   **河北**：河北省人社厅政策解读。
    *   **山西**：山西省人社厅部门文件。
    *   **内蒙古**：内蒙古人社厅政策解读。
4.  **自动推送**：
    *   支持钉钉群机器人 Webhook 推送。
    *   生成 Markdown 格式的日报，包含文章标题、链接和来源。

## 运行方式

### 1. 主程序运行（推荐）

运行主程序将执行所有已启用的抓取任务（财经 + 国家政策 + 5个地方人社局），并汇总发送一条消息。

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

## 环境变量配置

请在运行前确保设置了以下环境变量（或在代码中硬编码）：

*   `DASHSCOPE_API_KEY`: 阿里云 DashScope API Key（用于 AI 筛选）。
*   `SHIYANQUNWEBHOOK` / `SHIYANQUNSECRET`: 钉钉群 1 的 Webhook 和 Secret。
*   `DINGDINGSHANGYEWEBHOOK` / `DINGDINGSHANGYESECRET`: 钉钉群 2 的 Webhook 和 Secret。
*   `RUN_CHINATAX`: 是否运行税务总局抓取（1=运行，0=不运行）。
*   `RUN_TOPHR`: 是否运行第一资源抓取（1=运行，0=不运行）。

## 核心文件结构

*   `mohrss_local_news.py`: 主入口脚本。
*   `news_crawlers/`: 爬虫模块目录。
    *   `beijing_rsj.py`: 北京爬虫。
    *   `tianjin_hrss.py`: 天津爬虫。
    *   `hebei_rst.py`: 河北爬虫。
    *   `shanxi_rst.py`: 山西爬虫。
    *   `neimenggu_rst.py`: 内蒙古爬虫。
    *   `ai_crawler.py`: AI 筛选逻辑。
    *   `dingtalk.py`: 钉钉发送逻辑。
    *   ... 其他爬虫模块。

## 注意事项

*   **抓取时间**：程序会自动判断目标日期。
    *   周一：抓取上周五的数据。
    *   周二至周五：抓取昨天的数据。
    *   周末：默认不运行抓取。
*   **网络环境**：部分政府网站响应较慢，脚本设置了超时处理，请保持网络畅通。
