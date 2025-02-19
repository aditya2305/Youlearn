import React, { useEffect, useState, MutableRefObject } from 'react';
import { useResizeObserver } from '@/hooks/useResizeObserver';

interface BoundingBoxProps {
  bbox: number[];
  pageNumber: number;
  containerRef: MutableRefObject<HTMLDivElement | null>;
  scale?: number;
}

const BoundingBox: React.FC<BoundingBoxProps> = ({
  bbox,
  pageNumber,
  containerRef,
  scale = 1
}) => {
  const [position, setPosition] = useState({
    left: 0,
    top: 0,
    width: 0,
    height: 0,
  });

  // Watch for container size changes
  const containerSize = useResizeObserver(containerRef);

  useEffect(() => {
    const updatePosition = () => {
      if (!containerRef.current) return;

      const container = containerRef.current;
      const pageElement = container.querySelector(
        `[data-testid="core__page-layer-${pageNumber - 1}"]`
      ) as HTMLDivElement | null;

      if (!pageElement) return;

      const pageCanvas = pageElement.querySelector('.rpv-core__canvas-layer canvas');
      if (!pageCanvas) return;

      const canvasRect = pageCanvas.getBoundingClientRect();
      const containerRect = container.getBoundingClientRect();

      // Apply scale factor to coordinates
      const x0 = bbox[0] * canvasRect.width * scale;
      const y0 = bbox[1] * canvasRect.height * scale;
      const x1 = bbox[2] * canvasRect.width * scale;
      const y1 = bbox[3] * canvasRect.height * scale;

      setPosition({
        left: canvasRect.left - containerRect.left + x0,
        top: canvasRect.top - containerRect.top + y0,
        width: x1 - x0,
        height: y1 - y0,
      });
    };

    updatePosition();

    // Add scroll event listener
    const container = containerRef.current;
    if (container) {
      container.addEventListener('scroll', updatePosition);
      return () => container.removeEventListener('scroll', updatePosition);
    }
  }, [bbox, pageNumber, containerRef, scale, containerSize]);

  return (
    <div
      style={{
        position: 'absolute',
        left: position.left,
        top: position.top,
        width: position.width,
        height: position.height,
        border: '2px solid red',
        backgroundColor: 'rgba(255, 0, 0, 0.1)',
        pointerEvents: 'none',
        zIndex: 1000,
        transform: `scale(${scale})`,
        transformOrigin: 'top left',
      }}
    />
  );
};

export default BoundingBox;
