import React from 'react';
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Sequence,
  Easing,
} from 'remotion';

export interface Theme {
  bg: string;
  accent: string;
  text: string;
  sub: string;
}

export interface RepoData {
  owner: string;
  repo: string;
  name: string;
  description: string;
  stars: number;
  forks: number;
  language: string;
  topics: string[];
  homepage: string;
  readme: string;
}

export interface RepoVideoProps {
  repoUrl: string;
  repoData: RepoData;
  theme: Theme;
  durationInFrames: number;
}

// ---- Shared helpers --------------------------------------------------------

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fadeUp(frame: number, fps: number, delay = 0, duration = 20) {
  const f = Math.max(0, frame - delay);
  const opacity = interpolate(f, [0, duration], [0, 1], { extrapolateRight: 'clamp' });
  const y = interpolate(f, [0, duration], [30, 0], {
    extrapolateRight: 'clamp',
    easing: Easing.out(Easing.quad),
  });
  return { opacity, transform: `translateY(${y}px)` };
}

// ---- Scene: Intro (0 – 8s) --------------------------------------------------

const IntroScene: React.FC<{ repoData: RepoData; theme: Theme }> = ({ repoData, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleStyle = fadeUp(frame, fps, 0, 25);
  const descStyle = fadeUp(frame, fps, 20, 20);
  const urlStyle = fadeUp(frame, fps, 35, 20);

  const lineProgress = interpolate(frame, [10, 40], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', padding: 80 }}>
      {/* Accent line */}
      <div style={{
        width: `${lineProgress * 120}px`,
        height: 4,
        backgroundColor: theme.accent,
        borderRadius: 2,
        marginBottom: 32,
        ...titleStyle,
      }} />

      <div style={{ ...titleStyle, fontSize: 72, fontWeight: 800, color: theme.text, fontFamily: 'sans-serif', textAlign: 'center', letterSpacing: -2 }}>
        {repoData.name || `${repoData.owner}/${repoData.repo}`}
      </div>

      {repoData.description && (
        <div style={{ ...descStyle, fontSize: 28, color: theme.sub, fontFamily: 'sans-serif', textAlign: 'center', maxWidth: 900, marginTop: 24, lineHeight: 1.5 }}>
          {repoData.description}
        </div>
      )}

      <div style={{ ...urlStyle, fontSize: 22, color: theme.accent, fontFamily: 'monospace', marginTop: 40 }}>
        github.com/{repoData.owner}/{repoData.repo}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene: Stats (8 – 18s) -------------------------------------------------

const StatCard: React.FC<{ label: string; value: string; icon: string; theme: Theme; delay: number }> = ({ label, value, icon, theme, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame: frame - delay, fps, config: { damping: 14, stiffness: 120 } });

  return (
    <div style={{
      transform: `scale(${scale})`,
      backgroundColor: `${theme.accent}18`,
      border: `2px solid ${theme.accent}40`,
      borderRadius: 20,
      padding: '40px 60px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 12,
      minWidth: 200,
    }}>
      <div style={{ fontSize: 48 }}>{icon}</div>
      <div style={{ fontSize: 52, fontWeight: 800, color: theme.accent, fontFamily: 'sans-serif' }}>{value}</div>
      <div style={{ fontSize: 22, color: theme.sub, fontFamily: 'sans-serif', textTransform: 'uppercase', letterSpacing: 2 }}>{label}</div>
    </div>
  );
};

const StatsScene: React.FC<{ repoData: RepoData; theme: Theme }> = ({ repoData, theme }) => {
  const frame = useCurrentFrame();
  const titleAnim = fadeUp(frame, 30, 0, 20);

  const stats: { label: string; value: string; icon: string; delay: number }[] = [
    { label: 'Stars', value: fmt(repoData.stars), icon: '⭐', delay: 15 },
    { label: 'Forks', value: fmt(repoData.forks), icon: '🔀', delay: 25 },
  ];
  if (repoData.language) {
    stats.push({ label: 'Language', value: repoData.language, icon: '💻', delay: 35 });
  }

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 60, padding: 80 }}>
      <div style={{ ...titleAnim, fontSize: 52, fontWeight: 700, color: theme.text, fontFamily: 'sans-serif', letterSpacing: -1 }}>
        Repository Stats
      </div>
      <div style={{ display: 'flex', gap: 40, flexWrap: 'wrap', justifyContent: 'center' }}>
        {stats.map((s) => (
          <StatCard key={s.label} {...s} theme={theme} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene: Topics / Features (18 – 26s) -----------------------------------

const TopicsScene: React.FC<{ repoData: RepoData; theme: Theme }> = ({ repoData, theme }) => {
  const frame = useCurrentFrame();
  const titleAnim = fadeUp(frame, 30, 0, 20);

  const items = repoData.topics.length > 0
    ? repoData.topics.slice(0, 6)
    : ['Open Source', 'Developer Tool', 'Community'];

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 50, padding: 80 }}>
      <div style={{ ...titleAnim, fontSize: 52, fontWeight: 700, color: theme.text, fontFamily: 'sans-serif' }}>
        Topics
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 20, justifyContent: 'center', maxWidth: 1200 }}>
        {items.map((topic, i) => {
          const scale = spring({ frame: frame - (i * 8 + 10), fps: 30, config: { damping: 14, stiffness: 100 } });
          return (
            <div key={topic} style={{
              transform: `scale(${scale})`,
              padding: '14px 28px',
              backgroundColor: `${theme.accent}22`,
              border: `1.5px solid ${theme.accent}`,
              borderRadius: 50,
              fontSize: 26,
              color: theme.accent,
              fontFamily: 'sans-serif',
              fontWeight: 600,
              letterSpacing: 0.5,
            }}>
              {topic}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ---- Scene: CTA / Outro (26 – 30s) ----------------------------------------

const OutroScene: React.FC<{ repoData: RepoData; theme: Theme }> = ({ repoData, theme }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pulse = interpolate(
    Math.sin((frame / fps) * Math.PI * 2),
    [-1, 1],
    [0.97, 1.03],
  );

  const ctaAnim = fadeUp(frame, fps, 5, 25);
  const urlAnim = fadeUp(frame, fps, 20, 20);
  const hpAnim = fadeUp(frame, fps, 30, 20);

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg, justifyContent: 'center', alignItems: 'center', flexDirection: 'column', gap: 32, padding: 80 }}>
      <div style={{
        ...ctaAnim,
        fontSize: 80,
        fontWeight: 900,
        fontFamily: 'sans-serif',
        background: `linear-gradient(135deg, ${theme.accent}, ${theme.text})`,
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        transform: `${ctaAnim.transform} scale(${pulse})`,
        letterSpacing: -2,
      }}>
        Check it out!
      </div>

      <div style={{ ...urlAnim, fontSize: 34, color: theme.accent, fontFamily: 'monospace', fontWeight: 600 }}>
        github.com/{repoData.owner}/{repoData.repo}
      </div>

      {repoData.homepage && (
        <div style={{ ...hpAnim, fontSize: 26, color: theme.sub, fontFamily: 'sans-serif' }}>
          {repoData.homepage}
        </div>
      )}
    </AbsoluteFill>
  );
};

// ---- Main composition -------------------------------------------------------

export const RepoVideo: React.FC<RepoVideoProps> = ({ repoData, theme, durationInFrames }) => {
  const fps = 30;
  const intro = Math.round(fps * 8);
  const stats = Math.round(fps * 10);
  const topics = Math.round(fps * 8);
  const outro = durationInFrames - intro - stats - topics;

  return (
    <AbsoluteFill style={{ backgroundColor: theme.bg }}>
      <Sequence from={0} durationInFrames={intro}>
        <IntroScene repoData={repoData} theme={theme} />
      </Sequence>
      <Sequence from={intro} durationInFrames={stats}>
        <StatsScene repoData={repoData} theme={theme} />
      </Sequence>
      <Sequence from={intro + stats} durationInFrames={topics}>
        <TopicsScene repoData={repoData} theme={theme} />
      </Sequence>
      <Sequence from={intro + stats + topics} durationInFrames={Math.max(1, outro)}>
        <OutroScene repoData={repoData} theme={theme} />
      </Sequence>
    </AbsoluteFill>
  );
};
