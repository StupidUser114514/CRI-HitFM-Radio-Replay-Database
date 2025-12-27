import sys, os, requests, json, time
from datetime import datetime

def main(column_id):
    # 1. 设置API的基础信息
    api_url = "https://ytmsout.radio.cn/web/appProgram/pageByColumn"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.radio.cn/', # 必须，表明请求来源
        'Origin': 'https://www.radio.cn',   # 必须，CORS请求来源
        'Accept': 'application/json',
        # 以下是捕获到的关键请求头，特别注意 sign 和 timestamp
        'platformcode': 'WEB',
        'equipmentid': '0000',
        'timestamp': '1766843298017', # 【注意】这个值很可能需要动态生成
        'sign': 'F30B42030830025FD8377E0ED48C988B', # 【注意】这个值很可能需要动态生成并与timestamp对应
        'Host': 'ytmsout.radio.cn'
    }

    page_no = 0
    page_size = 20
    all_programs = []

    # 2. 循环请求所有分页
    while True:
        params = {
            'pageNo': page_no,
            'columnId': column_id, # 使用函数参数
            'pageSize': page_size
        }
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=10)
            data = resp.json()
            print(f"请求第 {page_no} 页，状态码: {resp.status_code}")

            if data.get('code') == 0 and data.get('data'):
                program_list = data['data'].get('data', [])
                total_pages = data['data'].get('totalPage', 1) # 尝试获取总页数

                if not program_list:
                    print("当前页无数据，结束。")
                    break

                all_programs.extend(program_list)
                print(f"  本页获取到 {len(program_list)} 条节目。")

                # 判断是否还有下一页
                if page_no >= total_pages - 1: # 页码从0开始
                    print(f"已到达最后一页（共{total_pages}页），结束。")
                    break
                page_no += 1

            else:
                print(f"API返回异常或数据为空: {data}")
                break

        except json.JSONDecodeError:
            print(f"第 {page_no} 页响应不是有效的JSON: {resp.text[:200]}")
            break
        except Exception as e:
            print(f"请求第 {page_no} 页时发生错误: {e}")
            break

    # 3. 下载音频文件
    print(f"\n开始处理下载，共 {len(all_programs)} 个节目。")
    for program in all_programs:
        download_url = program.get('downloadUrl') # 下载链接
        program_date = program.get('programDate') # 可能是时间戳
        program_name = program.get('name', '未知节目').strip()

        if not download_url:
            print(f"节目 '{program_name}' 无下载链接，跳过。")
            continue

        # 生成安全的文件名
        if program_date:
            try:
                # 假设programDate是毫秒时间戳
                date_obj = datetime.fromtimestamp(int(program_date) / 1000)
                date_str = date_obj.strftime('%Y-%m-%d')
            except (ValueError, TypeError, OSError):
                date_str = '无日期'
        else:
            date_str = '无日期'

        # 清理文件名中的非法字符
        safe_name = "".join([c for c in program_name if c.isalnum() or c in (' ', '-', '_', '，', '。')]).rstrip()
        # 如果名字太长，可以截断
        safe_name = safe_name[:100]
        file_name = f"{date_str}_{safe_name}.mp3"

        # 检查文件是否已存在
        if not os.path.exists(file_name):
            print(f"正在下载: {file_name}")
            try:
                # 下载文件可能需要相同的请求头，或者需要更简单的头
                file_headers = {'User-Agent': headers['User-Agent']}
                audio_resp = requests.get(download_url, headers=file_headers, stream=True, timeout=60)
                audio_resp.raise_for_status() # 检查HTTP错误

                with open(file_name, 'wb') as f:
                    for chunk in audio_resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"  下载完成。")
                time.sleep(0.5) # 礼貌延迟，避免请求过快

            except Exception as e:
                print(f"  下载失败: {e}")
        else:
            print(f"文件已存在，跳过: {file_name}")

    print("所有任务处理完毕。")

if __name__ == '__main__':
    # 直接从你提供的URL中获取columnId，这里写死为 1432825
    # 你也可以改为从环境变量或参数读取
    target_column_id = "1432825"
    main(target_column_id)
