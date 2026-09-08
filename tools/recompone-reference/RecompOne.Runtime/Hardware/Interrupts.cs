using RecompOne.Runtime.Bios;
using RecompOne.Runtime.Context;
using RecompOne.Runtime.Dispatch;
using RecompOne.Runtime.Memory;

namespace RecompOne.Runtime;

public static class Interrupts
{
    static bool _delivering;
    static uint _pending;

    public static void Deliver(int irq, CpuContext cpu, IMemory mem)
    {
        uint intrEnv = BiosB.IntrEnvInInterruptAddr;
        if (intrEnv == 0) return;

        // The R3000 masks normal interrupt delivery while its exception
        // handler is active. A synchronous host DMA can complete from inside
        // that handler, but it must not recursively enter the same BIOS
        // interrupt environment and exhaust the managed stack.
        _pending |= 1u << irq;
        if (_delivering || mem.ReadU16(intrEnv) != 0) return;

        _delivering = true;
        try
        {
            // Drain synchronously completed devices after the active handler
            // returns, matching the hardware's pending-interrupt behavior
            // without recursive managed calls. Bound one drain pass so a
            // continuously asserted source yields back to the game loop.
            for (int delivered = 0; _pending != 0u && delivered < 64; delivered++)
            {
                int next = System.Numerics.BitOperations.TrailingZeroCount(_pending);
                _pending &= ~(1u << next);
                uint handler = mem.ReadU32(intrEnv + 2u + (uint)next * 4u);
                if (handler == 0u) continue;

                // Interrupt callbacks run in an exception context, separate
                // from the interrupted game's register state.
                var snap = cpu.Snapshot();
                mem.WriteU16(intrEnv, 1);
                try
                {
                    Dispatcher.Call(cpu, mem, handler);
                }
                finally
                {
                    mem.WriteU16(intrEnv, 0);
                    cpu.Restore(snap);
                }
            }
        }
        finally
        {
            _delivering = false;
        }
    }
}
