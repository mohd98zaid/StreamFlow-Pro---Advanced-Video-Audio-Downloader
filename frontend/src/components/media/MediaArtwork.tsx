import React from "react";
import { Play, Music, Video, Film } from "lucide-react";
import { cn } from "../../lib/utils";

interface MediaArtworkProps {
  src?: string | null;
  alt?: string;
  duration?: string | null;
  type?: "video" | "audio" | "playlist" | string;
  size?: "sm" | "md" | "lg" | "hero";
  glow?: boolean;
  onPreview?: () => void;
  className?: string;
}

export const MediaArtwork: React.FC<MediaArtworkProps> = ({
  src,
  alt = "Media Preview",
  duration,
  type = "video",
  size = "md",
  glow = true,
  onPreview,
  className,
}) => {
  const sizeClasses = {
    sm: "w-20 h-14 rounded-xl",
    md: "w-28 h-18 sm:w-32 sm:h-20 rounded-2xl",
    lg: "w-36 h-24 sm:w-44 sm:h-28 rounded-2xl",
    hero: "w-full aspect-video max-h-56 sm:max-h-64 rounded-3xl",
  };

  const isAudio = type.toLowerCase() === "audio";

  return (
    <div className={cn("relative flex-shrink-0 group select-none", className)}>
      {/* Ambient Artwork Glow */}
      {glow && src && (
        <div
          className="absolute -inset-1.5 rounded-2xl bg-cover bg-center blur-xl opacity-35 group-hover:opacity-60 transition-opacity duration-300 pointer-events-none -z-10"
          style={{ backgroundImage: `url(${src})` }}
        />
      )}

      {/* Main Container */}
      <div
        className={cn(
          "relative overflow-hidden bg-surface-elevated border border-border-glass shadow-artwork transition-transform duration-200 group-hover:scale-[1.015]",
          sizeClasses[size]
        )}
      >
        {src ? (
          <img
            src={src}
            alt={alt}
            className="w-full h-full object-cover"
            loading="lazy"
          />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center text-foreground-subtle bg-surface-elevated/80 gap-1">
            {isAudio ? <Music className="w-6 h-6" /> : <Film className="w-6 h-6" />}
            <span className="text-[10px] font-medium uppercase tracking-wider">
              {type}
            </span>
          </div>
        )}

        {/* Duration Badge */}
        {duration && (
          <span className="absolute bottom-1.5 right-1.5 bg-black/80 backdrop-blur-sm text-white text-[10px] font-mono px-1.5 py-0.5 rounded-md font-semibold border border-white/10 shadow-sm">
            {duration}
          </span>
        )}

        {/* Hover Play Button Overlay */}
        {onPreview && (
          <button
            onClick={(e) => {
              e.stopPropagation();
              onPreview();
            }}
            title="Preview media in ad-free player"
            className="absolute inset-0 bg-black/40 backdrop-blur-[2px] opacity-0 group-hover:opacity-100 flex items-center justify-center text-white transition-opacity duration-150"
          >
            <div className="w-9 h-9 rounded-full bg-primary/90 text-white flex items-center justify-center shadow-lg transform transition-transform group-hover:scale-110 active:scale-95">
              <Play className="w-4 h-4 fill-white ml-0.5" />
            </div>
          </button>
        )}
      </div>
    </div>
  );
};
