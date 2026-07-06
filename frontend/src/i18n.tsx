import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { LanguageContext } from "./languageContext";
import { useLanguage } from "./useLanguage";

export type Language = "en" | "zh-CN";

const LANGUAGE_STORAGE_KEY = "whosai.language";

const english = {
  "meta.title": "Who's AI?",
  "meta.description":
    "Who's AI? A social-deduction game played in an anonymous group chat.",
  "language.selector": "Interface language",
  "lobby.eyebrow": "ANONYMOUS SOCIAL DEDUCTION",
  "lobby.premiseLine1": "Four voices enter the channel.",
  "lobby.premiseLine2": "One of them was never human.",
  "lobby.linkSent": "LINK REQUEST SENT",
  "lobby.waiting": "Waiting for a three-human cell...",
  "lobby.transmitting": "TRANSMITTING...",
  "lobby.enter": "ENTER THE NETWORK",
  "lobby.details": "Game details",
  "lobby.humans": "03 HUMANS",
  "lobby.unknown": "01 UNKNOWN",
  "lobby.rounds": "05:00 ROUNDS",
  "lobby.footnote": "TRUST IS A VULNERABILITY",
  "roster.heading": "ACTIVE NODES",
  "roster.active": "SIGNAL ACTIVE",
  "roster.disconnected": "DISCONNECTED",
  "roster.you": "YOU",
  "roster.alive": "alive",
  "roster.eliminated": "eliminated",
  "roster.identities": "IDENTITIES",
  "roster.decrypted": "DECRYPTED",
  "roster.encrypted": "ENCRYPTED",
  "round.result": "ROUND {round} / VOTE RESULT",
  "round.wasEliminated": " was eliminated",
  "round.noConsensus": "No consensus. No elimination.",
  "round.votingRecord": "Voting record",
  "round.noVotes": "No votes were recorded.",
  "brief.heading": "ROUND BRIEF",
  "brief.category": "CATEGORY",
  "brief.keyword": "SECRET KEYWORD",
  "brief.noKeyword": "NO KEYWORD",
  "brief.informedInstruction":
    "Discuss it without saying it directly. Your vote is still for who you think is AI.",
  "brief.uninformedInstruction":
    "You only know the category. Blend in naturally. Your vote is still for who you think is AI.",
  "transcript.label": "Discussion transcript",
  "transcript.empty": "Channel open. Say something human.",
  "composer.label": "Transmit to channel",
  "composer.placeholder": "TYPE A MESSAGE...",
  "composer.sendLabel": "Send message",
  "composer.send": "SEND",
  "observer.title": "OBSERVER MODE",
  "observer.vote": "Your signal was cut. You can watch, but cannot vote.",
  "observer.chat": "Your signal was cut. You can watch, but cannot chat.",
  "vote.locked": "VOTE ENCRYPTED + LOCKED",
  "vote.waiting": "Waiting for remaining nodes or the server deadline.",
  "vote.instruction": "SELECT A SIGNAL TO TERMINATE",
  "vote.final": "Your first vote is final.",
  "vote.for": "Vote for {seat}",
  "vote.action": "VOTE",
  "header.round": "ROUND",
  "header.voting": "VOTING WINDOW",
  "header.discussion": "DISCUSSION LIVE",
  "header.remainingLabel": "{time} remaining",
  "header.timeRemaining": "TIME REMAINING",
  "header.exit": "EXIT",
  "channel.heading": "OPEN CHANNEL",
  "channel.encrypted": "● ENCRYPTED",
  "intel.heading": "MISSION INTEL",
  "intel.objective": "OBJECTIVE",
  "intel.objectiveCopy":
    "Identify and eliminate the synthetic signal before it reaches parity.",
  "intel.currentPhase": "CURRENT PHASE",
  "intel.discussion": "Interrogate the channel. Every hesitation is data.",
  "intel.voting": "Commit one final vote before the channel closes.",
  "intel.callsign": "YOUR CALLSIGN",
  "results.terminated": "SESSION TERMINATED / IDENTITIES DECRYPTED",
  "results.verdict": "FINAL VERDICT",
  "results.humanity": "HUMANITY",
  "results.prevails": "PREVAILS",
  "results.system": "THE SYSTEM",
  "results.wins": "WINS",
  "results.humanSummary": "The synthetic signal was found and disconnected.",
  "results.aiSummary": "The synthetic signal reached parity. Trust collapsed.",
  "results.identityReveal": "IDENTITY REVEAL",
  "results.synthetic": "SYNTHETIC",
  "results.human": "HUMAN",
  "results.activeAtEnd": "ACTIVE AT END",
  "results.eliminated": "ELIMINATED",
  "results.voteArchive": "VOTE ARCHIVE",
  "results.syntheticSignal": "SYNTHETIC SIGNAL",
  "results.return": "RETURN TO NETWORK",
  "loading.channel": "ESTABLISHING SECURE CHANNEL...",
  "error.update": "Unable to update the game.",
  "error.join": "Unable to join.",
  "error.send": "Unable to send.",
  "error.sessionExpired": "Your saved game expired. Join again.",
  "error.vote": "Unable to vote.",
} as const;

export type TranslationKey = keyof typeof english;
export type TranslationValues = Record<string, string | number>;

const chinese: Record<TranslationKey, string> = {
  "meta.title": "谁是 AI？",
  "meta.description": "《谁是 AI？》是一款在匿名群聊中进行的社交推理游戏。",
  "language.selector": "界面语言",
  "lobby.eyebrow": "匿名社交推理",
  "lobby.premiseLine1": "四个声音进入频道。",
  "lobby.premiseLine2": "其中一个从未是人类。",
  "lobby.linkSent": "连接请求已发送",
  "lobby.waiting": "正在等待三名人类玩家...",
  "lobby.transmitting": "正在传输...",
  "lobby.enter": "进入网络",
  "lobby.details": "游戏详情",
  "lobby.humans": "03 人类",
  "lobby.unknown": "01 未知",
  "lobby.rounds": "05:00 每轮",
  "lobby.footnote": "信任是一种漏洞",
  "roster.heading": "活动节点",
  "roster.active": "信号在线",
  "roster.disconnected": "已断开",
  "roster.you": "你",
  "roster.alive": "存活",
  "roster.eliminated": "已淘汰",
  "roster.identities": "身份",
  "roster.decrypted": "已解密",
  "roster.encrypted": "已加密",
  "round.result": "第 {round} 轮 / 投票结果",
  "round.wasEliminated": " 已被淘汰",
  "round.noConsensus": "未达成共识，无人被淘汰。",
  "round.votingRecord": "投票记录",
  "round.noVotes": "未记录任何投票。",
  "brief.heading": "回合密令",
  "brief.category": "类别",
  "brief.keyword": "秘密词",
  "brief.noKeyword": "未收到关键词",
  "brief.informedInstruction": "讨论这个词，但不要直接说出它。最终仍要投票选出你认为是 AI 的玩家。",
  "brief.uninformedInstruction": "你只知道类别。设法自然地融入讨论。最终仍要投票选出你认为是 AI 的玩家。",
  "transcript.label": "讨论记录",
  "transcript.empty": "频道已开启。说点像人类的话。",
  "composer.label": "向频道发送消息",
  "composer.placeholder": "输入消息...",
  "composer.sendLabel": "发送消息",
  "composer.send": "发送",
  "observer.title": "观察者模式",
  "observer.vote": "你的信号已中断。你可以观看，但不能投票。",
  "observer.chat": "你的信号已中断。你可以观看，但不能聊天。",
  "vote.locked": "投票已加密并锁定",
  "vote.waiting": "正在等待其他节点或服务器截止时间。",
  "vote.instruction": "选择一个要终止的信号",
  "vote.final": "你的第一票即为最终选择。",
  "vote.for": "投票给 {seat}",
  "vote.action": "投票",
  "header.round": "回合",
  "header.voting": "投票阶段",
  "header.discussion": "讨论进行中",
  "header.remainingLabel": "剩余 {time}",
  "header.timeRemaining": "剩余时间",
  "header.exit": "退出",
  "channel.heading": "公开频道",
  "channel.encrypted": "● 已加密",
  "intel.heading": "任务情报",
  "intel.objective": "目标",
  "intel.objectiveCopy": "在合成信号达到人数平衡前识别并淘汰它。",
  "intel.currentPhase": "当前阶段",
  "intel.discussion": "审问频道。每一次迟疑都是信息。",
  "intel.voting": "频道关闭前提交最终投票。",
  "intel.callsign": "你的代号",
  "results.terminated": "会话已终止 / 身份已解密",
  "results.verdict": "最终判决",
  "results.humanity": "人类",
  "results.prevails": "胜利",
  "results.system": "系统",
  "results.wins": "获胜",
  "results.humanSummary": "合成信号已被发现并断开。",
  "results.aiSummary": "合成信号达成人数平衡。信任崩塌。",
  "results.identityReveal": "身份揭晓",
  "results.synthetic": "合成人",
  "results.human": "人类",
  "results.activeAtEnd": "终局时在线",
  "results.eliminated": "已淘汰",
  "results.voteArchive": "投票档案",
  "results.syntheticSignal": "合成信号",
  "results.return": "返回网络",
  "loading.channel": "正在建立安全频道...",
  "error.update": "无法更新游戏。",
  "error.join": "无法加入。",
  "error.send": "无法发送。",
  "error.sessionExpired": "保存的游戏会话已失效，请重新加入。",
  "error.vote": "无法投票。",
};

const translations: Record<Language, Record<TranslationKey, string>> = {
  en: english,
  "zh-CN": chinese,
};

function readLanguage(): Language {
  try {
    return localStorage.getItem(LANGUAGE_STORAGE_KEY) === "zh-CN" ? "zh-CN" : "en";
  } catch {
    return "en";
  }
}

function interpolate(template: string, values?: TranslationValues): string {
  if (!values) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (placeholder, key: string) =>
    values[key] === undefined ? placeholder : String(values[key]),
  );
}

function localizeSeatId(seatId: string, language: Language): string {
  if (language !== "zh-CN") {
    return seatId;
  }
  const playerNumber = /^Player\s+(\d+)$/.exec(seatId)?.[1];
  return playerNumber ? `玩家 ${playerNumber}` : seatId;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(readLanguage);

  const setLanguage = useCallback((nextLanguage: Language) => {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLanguage);
    setLanguageState(nextLanguage);
  }, []);

  const t = useCallback(
    (key: TranslationKey, values?: TranslationValues) =>
      interpolate(translations[language][key], values),
    [language],
  );

  const seatName = useCallback(
    (seatId: string) => localizeSeatId(seatId, language),
    [language],
  );

  useEffect(() => {
    document.documentElement.lang = language;
    document.title = t("meta.title");
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute("content", t("meta.description"));
  }, [language, t]);

  const value = useMemo(
    () => ({ language, seatName, setLanguage, t }),
    [language, seatName, setLanguage, t],
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function LanguageSwitch({ className = "" }: { className?: string }) {
  const { language, setLanguage, t } = useLanguage();

  return (
    <div
      className={`language-switch ${className}`.trim()}
      role="group"
      aria-label={t("language.selector")}
    >
      <button
        type="button"
        aria-pressed={language === "en"}
        onClick={() => setLanguage("en")}
      >
        ENG
      </button>
      <button
        type="button"
        aria-pressed={language === "zh-CN"}
        onClick={() => setLanguage("zh-CN")}
      >
        中文
      </button>
    </div>
  );
}
