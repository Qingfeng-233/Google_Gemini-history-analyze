# MIT License
#
# Copyright (c) 2025 Qingfeng-233
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.


import json
import re
import os
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from tqdm import tqdm


# --- 输入/输出文件 ---
INPUT_HTML_FILE = '我的活动记录.html'
OUTPUT_JSON_PATH = 'processed_history.json'
OUTPUT_TXT_PATH = 'processed_history.txt'
SETTINGS_FILE = 'settings.json'
# 中间文件(可选，用于调试或缓存)
STRUCTURED_JSON_PATH = 'structured_gemini_history.json'
INDEXED_JSONL_PATH = 'indexed_and_tagged_history.jsonl'

ENABLE_AI_ANALYSIS = True  # 设置为 True 以启用API调用，False 则跳过
AI_PROVIDER = "gemini"  
API_KEYS_FILE = 'valid_keys.txt'
MAX_CONCURRENT_REQUESTS = 10
MAX_RETRY_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 2

GEMINI_API_MODEL = "gemini-1.5-flash"  # 默认模型
GOOGLE_API_BASE_URL = "https://generativelanguage.googleapis.com"

OPENAI_BASE_URL = None
OPENAI_API_MODEL = None


key_lock = threading.Lock()
write_lock = threading.Lock()
api_keys = []
current_key_index = 0


def load_settings():
    """从 settings.json 加载配置。"""
    global AI_PROVIDER, OPENAI_BASE_URL, OPENAI_API_MODEL, GEMINI_API_MODEL
    
    if not os.path.exists(SETTINGS_FILE):
        print(f"[警告] 配置文件 '{SETTINGS_FILE}' 未找到。将使用默认设置 (Gemini)。")
        AI_PROVIDER = "gemini"
        return

    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
        # 从settings.json读取AI提供商
        AI_PROVIDER = settings.get('ai_provider', 'gemini').lower()
        
        # 读取Gemini特定配置
        if 'gemini' in settings:
            gemini_config = settings['gemini']
            # 如果在配置文件中指定了模型，则覆盖默认值
            GEMINI_API_MODEL = gemini_config.get('model', GEMINI_API_MODEL)

        # 读取OpenAI特定配置
        if 'openai' in settings:
            openai_config = settings['openai']
            OPENAI_BASE_URL = openai_config.get('base_url')
            OPENAI_API_MODEL = openai_config.get('model')
            
        print(f"成功从 '{SETTINGS_FILE}' 加载配置。AI提供商设置为: {AI_PROVIDER.upper()}")
        if AI_PROVIDER == 'gemini':
            print(f"Gemini 模型设置为: {GEMINI_API_MODEL}")

    except json.JSONDecodeError:
        print(f"[错误] 解析 '{SETTINGS_FILE}' 失败。请检查JSON格式。")
    except Exception as e:
        print(f"加载配置文件时出错: {e}")

def clean_html_content(html_text: str) -> str:
    """
    使用BeautifulSoup清理HTML内容，移除标签并规范化空白。
    """
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, 'html.parser')
    text = soup.get_text(separator='\n')
    lines = [line.strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)

def parse_and_clean_html(html_filepath):
    """
    从Google活动记录的HTML文件中解析对话，并直接清理内容。
    """
    print(f"--- 步骤 1: 解析和清理HTML文件: {html_filepath} ---")
    if not os.path.exists(html_filepath):
        print(f"[错误] 输入文件 '{html_filepath}' 未找到。")
        return None

    with open(html_filepath, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    full_text = soup.get_text()

    dialogue_chunks = full_text.split('Prompted')
    parsed_conversations = []
    
    timestamp_regex = r'\d{4}年\d{1,2}月\d{1,2}日 \d{2}:\d{2}:\d{2} JST'

    for i, chunk in enumerate(dialogue_chunks[1:], 1):
        if not chunk.strip():
            continue

        match = re.search(timestamp_regex, chunk)
        if match:
            timestamp = match.group(0)
            user_prompt_raw = chunk[:match.start()].strip()
            ai_response_raw = chunk[match.end():].strip()
            
            user_prompt_cleaned = user_prompt_raw.replace('”', '"').replace('“', '"')
            ai_response_cleaned = ai_response_raw

            conversation = {
                "id": i,
                "timestamp": timestamp,
                "user_prompt": user_prompt_cleaned,
                "ai_response": ai_response_cleaned
            }
            parsed_conversations.append(conversation)
        else:
            print(f"[警告] 在第 {i} 个对话块中未找到时间戳，已跳过。")
            
    print(f"成功解析并清理了 {len(parsed_conversations)} 轮对话。")
    with open(STRUCTURED_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(parsed_conversations, f, ensure_ascii=False, indent=2)
    print(f"已将结构化数据保存到 '{STRUCTURED_JSON_PATH}'")
    return parsed_conversations

def load_api_keys(provider):
    """从文件加载指定提供商的API密钥。"""
    global api_keys, current_key_index
    
    if not os.path.exists(API_KEYS_FILE):
        print(f"[错误] API密钥文件 '{API_KEYS_FILE}' 不存在。")
        return False
    try:
        with open(API_KEYS_FILE, 'r') as f:
            keys = [key.strip() for key in f if key.strip()]
            if not keys:
                print(f"[错误] '{API_KEYS_FILE}' 为空。")
                return False
            api_keys = keys
            current_key_index = 0
            print(f"成功为 {provider.upper()} 加载了 {len(api_keys)} 个 API 密钥。")
            return True
    except Exception as e:
        print(f"加载API密钥时出错: {e}")
        return False

def load_processed_ids(path):
    """加载已处理的ID以支持断点续传。"""
    processed_ids = set()
    if not os.path.exists(path):
        return processed_ids
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                data = json.loads(line)
                item_id = data.get('id')
                if item_id is not None:
                    processed_ids.add(item_id)
            except json.JSONDecodeError:
                continue
    return processed_ids

def get_analysis_prompt(conversation_data):
    """生成用于AI分析的通用prompt。"""
    return f"""
    你是一个信息检索和数据处理专家。请为下面的对话创建一个简洁的索引标题，并提取核心关键词作为标签。

    [对话内容]:
    用户: {conversation_data['user_prompt']}
    AI: {conversation_data['ai_response']}
    ---
    请严格按照以下JSON格式返回结果，不要包含任何额外的解释或文本：
    {{
        "index_title": "为对话生成一个不超过20个字的、高度概括的标题。",
        "tags": ["提取3到7个最相关的关键词或短语，形式为字符串数组。"]
    }}
    """

def fetch_gemini_analysis(conversation_data, prompt):
    """使用Gemini API获取分析结果。"""
    global api_keys, current_key_index
    
    request_body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"}
    }
    
    for attempt in range(MAX_RETRY_ATTEMPTS):
        with key_lock:
            if not api_keys:
                if attempt == 0: tqdm.write("\n[严重警告] 所有Gemini API密钥均已耗尽或失效！")
                return None
            key_index = current_key_index % len(api_keys)
            selected_key = api_keys[key_index]
            current_key_index += 1

        target_url = f"{GOOGLE_API_BASE_URL}/v1beta/models/{GEMINI_API_MODEL}:generateContent?key={selected_key}"
        headers = {'Content-Type': 'application/json'}
        
        try:
            response = requests.post(url=target_url, headers=headers, json=request_body, timeout=180)
            if response.status_code == 200:
                analysis_str = response.json()['candidates'][0]['content']['parts'][0]['text']
                return json.loads(analysis_str)
            elif response.status_code == 429:
                tqdm.write(f"\n[速率限制] Key [...{selected_key[-4:]}] 遭遇429错误，将移除。")
                with key_lock:
                    if selected_key in api_keys: api_keys.remove(selected_key)
                continue
            else:
                tqdm.write(f"\n[HTTP错误] ID {conversation_data['id']} 返回 {response.status_code}。重试...")
                time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            tqdm.write(f"\n[请求异常] ID {conversation_data['id']} 发生错误: {e}。重试...")
            time.sleep(RETRY_DELAY_SECONDS)
            
    tqdm.write(f"\n[最终失败] Gemini 对话 ID {conversation_data['id']} 多次尝试后失败。")
    return None

def fetch_openai_analysis(conversation_data, prompt):
    """使用OpenAI兼容API获取分析结果（支持轮询）。"""
    global api_keys, current_key_index

    if not OPENAI_BASE_URL or not OPENAI_API_MODEL:
        tqdm.write("\n[错误] OpenAI API的 base_url 或 model 未在settings.json中配置。")
        return None

    for attempt in range(MAX_RETRY_ATTEMPTS):
        with key_lock:
            if not api_keys:
                if attempt == 0: tqdm.write("\n[严重警告] 所有OpenAI API密钥均已耗尽或失效！")
                return None
            key_index = current_key_index % len(api_keys)
            selected_key = api_keys[key_index]
            current_key_index += 1

        headers = {
            "Authorization": f"Bearer {selected_key}",
            "Content-Type": "application/json"
        }
        
        request_body = {
            "model": OPENAI_API_MODEL,
            "messages": [
                {"role": "system", "content": "You are an expert in information retrieval and data processing."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }

        try:
            response = requests.post(f"{OPENAI_BASE_URL}/chat/completions", headers=headers, json=request_body, timeout=180)
            if response.status_code == 200:
                analysis_str = response.json()['choices'][0]['message']['content']
                return json.loads(analysis_str)
            elif response.status_code in [401, 403]:
                 tqdm.write(f"\n[认证失败] Key [...{selected_key[-4:]}] 无效或权限不足，将移除。")
                 with key_lock:
                    if selected_key in api_keys: api_keys.remove(selected_key)
                 continue
            elif response.status_code == 429:
                tqdm.write(f"\n[速率限制] Key [...{selected_key[-4:]}] 遭遇429错误，将轮换。")
                continue
            else:
                tqdm.write(f"\n[HTTP错误] OpenAI ID {conversation_data['id']} 返回 {response.status_code}。重试...")
                time.sleep(RETRY_DELAY_SECONDS)
        except Exception as e:
            tqdm.write(f"\n[请求异常] OpenAI ID {conversation_data['id']} 发生错误: {e}。重试...")
            time.sleep(RETRY_DELAY_SECONDS)
            
    tqdm.write(f"\n[最终失败] OpenAI 对话 ID {conversation_data['id']} 多次尝试后失败。")
    return None


def fetch_ai_analysis(conversation_data):
    """为单次对话获取索引和标签（分发到不同API）。"""
    prompt = get_analysis_prompt(conversation_data)
    
    if AI_PROVIDER == "openai":
        analysis_result = fetch_openai_analysis(conversation_data, prompt)
    else: # 默认为 gemini
        analysis_result = fetch_gemini_analysis(conversation_data, prompt)
        
    return (conversation_data, analysis_result)


def run_ai_analysis_pipeline(conversations):
    """执行AI分析流程。"""
    print("\n--- 步骤 2: 执行AI索引和标签生成 ---")
    
    if not load_api_keys(AI_PROVIDER):
        print(f"[信息] 因无法加载 {AI_PROVIDER.upper()} 密钥，跳过AI分析。")
        return conversations

    if AI_PROVIDER == "openai" and (not OPENAI_BASE_URL or not OPENAI_API_MODEL):
        print("[错误] OpenAI API的 base_url 或 model 未在settings.json中配置，无法继续。")
        return conversations

    processed_ids = load_processed_ids(INDEXED_JSONL_PATH)
    tasks_to_process = [conv for conv in conversations if conv.get('id') not in processed_ids]

    if not tasks_to_process:
        print("所有对话都已分析过，将从缓存加载。")
        all_results = []
        with open(INDEXED_JSONL_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                all_results.append(json.loads(line))
        return all_results

    print(f"需要分析 {len(tasks_to_process)} 个新对话，使用 {AI_PROVIDER.upper()} API。")
    
    with open(INDEXED_JSONL_PATH, 'a', encoding='utf-8') as f_out, \
         ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
        
        futures = {executor.submit(fetch_ai_analysis, task): task for task in tasks_to_process}
        
        for future in tqdm(as_completed(futures), total=len(tasks_to_process), desc="AI分析中"):
            original_data, analysis_result = future.result()
            if analysis_result:
                combined_result = {**original_data, **analysis_result}
                with write_lock:
                    f_out.write(json.dumps(combined_result, ensure_ascii=False) + '\n')
                    f_out.flush()
    
    print("AI分析完成。")
    all_analyzed_data = []
    with open(INDEXED_JSONL_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            all_analyzed_data.append(json.loads(line))
    return all_analyzed_data


def save_as_final_json(data, path):
    """将最终数据保存为格式化的JSON文件。"""
    print(f"\n--- 步骤 3: 生成最终JSON文件 ---")
    data.sort(key=lambda x: x.get('id', 0))
    
    final_data = []
    for item in data:
        final_data.append({
            "id": item.get('id'),
            "timestamp": item.get('timestamp'),
            "title": item.get('index_title', '无标题'),
            "tags": item.get('tags', []),
            "user_prompt_cleaned": item.get('user_prompt'),
            "ai_response_cleaned": item.get('ai_response')
        })

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
    print(f"成功！处理结果已保存到 '{path}'。")

def save_as_txt(data, path):
    """将最终数据保存为人类可读的TXT文件。"""
    print(f"\n--- 步骤 4: 生成TXT报告文件 ---")
    data.sort(key=lambda x: x.get('id', 0))

    with open(path, 'w', encoding='utf-8') as f:
        for item in data:
            f.write(f"ID: {item.get('id', 'N/A')}\n")
            f.write(f"标题: {item.get('index_title', '无标题')}\n")
            f.write(f"标签: {', '.join(item.get('tags', []))}\n")
            f.write("-" * 40 + "\n")
            f.write("【用户提问】\n")
            f.write(f"{item.get('user_prompt', '')}\n\n")
            f.write("【AI 回答】\n")
            f.write(f"{item.get('ai_response', '')}\n")
            f.write("=" * 60 + "\n\n")
    print(f"成功！TXT报告已保存到 '{path}'。")

# --- 3. 主执行函数 ---
def main():
    """主执行函数，协调整个流水线。"""
    print("====== 数据处理流水线启动 ======")
    
    load_settings()
    
    conversations = parse_and_clean_html(INPUT_HTML_FILE)
    if not conversations:
        print("因无法解析HTML，流水线终止。")
        return

    if ENABLE_AI_ANALYSIS:
        processed_data = run_ai_analysis_pipeline(conversations)
    else:
        print("\n[信息] 已跳过AI分析步骤。")
        processed_data = conversations

    if not processed_data:
        print("没有可处理的数据，流水线终止。")
        return
        
    save_as_final_json(processed_data, OUTPUT_JSON_PATH)
    save_as_txt(processed_data, OUTPUT_TXT_PATH)
    
    print("\n====== 所有任务处理完成！ ======")

if __name__ == '__main__':
    main()
