class PCM16CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.pending = [];
    this.frameSize = 2048;
  }

  process(inputs) {
    const channels = inputs[0];
    if (!channels || channels.length === 0 || !channels[0]) return true;
    const source = channels.length === 1
      ? channels[0]
      : channels[0].map((_, index) => channels.reduce((sum, channel) => sum + channel[index], 0) / channels.length);
    for (let index = 0; index < source.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, source[index]));
      this.pending.push(sample < 0 ? sample * 32768 : sample * 32767);
    }
    while (this.pending.length >= this.frameSize) {
      const frame = new Int16Array(this.frameSize);
      for (let index = 0; index < frame.length; index += 1) frame[index] = this.pending[index];
      this.pending.splice(0, this.frameSize);
      let squared = 0;
      for (const sample of frame) squared += (sample / 32768) ** 2;
      this.port.postMessage({ frame: frame.buffer, level: Math.sqrt(squared / frame.length) }, [frame.buffer]);
    }
    return true;
  }
}

registerProcessor("pcm16-capture", PCM16CaptureProcessor);
