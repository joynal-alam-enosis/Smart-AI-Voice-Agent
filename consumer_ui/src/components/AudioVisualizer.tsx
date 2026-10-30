import { useEffect, useRef, useState } from 'react';

interface AudioVisualizerProps {
  stream: MediaStream | null;
  active: boolean;
}

/** Renders a subtle live amplitude field from the locally captured microphone stream. */
export function AudioVisualizer({ stream, active }: AudioVisualizerProps) {
  const [levels, setLevels] = useState<number[]>(() => Array.from({ length: 28 }, () => 0.12));
  const animationFrameRef = useRef<number | null>(null);

  useEffect(() => {
    if (!stream || !active) {
      setLevels(Array.from({ length: 28 }, (_, index) => 0.08 + (index % 4) * 0.025));
      return undefined;
    }
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.78;
    source.connect(analyser);
    const frequencies = new Uint8Array(analyser.frequencyBinCount);

    const render = () => {
      analyser.getByteFrequencyData(frequencies);
      const nextLevels = Array.from({ length: 28 }, (_, index) => {
        const start = Math.floor((index / 28) * frequencies.length);
        const end = Math.max(start + 1, Math.floor(((index + 1) / 28) * frequencies.length));
        const average = frequencies.slice(start, end).reduce((total, current) => total + current, 0) / (end - start);
        return Math.max(0.08, Math.min(1, average / 175));
      });
      setLevels(nextLevels);
      animationFrameRef.current = window.requestAnimationFrame(render);
    };
    render();

    return () => {
      if (animationFrameRef.current !== null) window.cancelAnimationFrame(animationFrameRef.current);
      source.disconnect();
      void audioContext.close();
    };
  }, [active, stream]);

  return (
    <div className="flex h-14 items-center justify-center gap-1.5" aria-hidden="true">
      {levels.map((level, index) => (
        <span
          className={`w-1.5 rounded-full transition-[height,background-color] duration-100 ${active ? 'bg-violet-300' : 'bg-slate-400/60'}`}
          key={index}
          style={{ height: `${Math.round(6 + level * 35)}px` }}
        />
      ))}
    </div>
  );
}
