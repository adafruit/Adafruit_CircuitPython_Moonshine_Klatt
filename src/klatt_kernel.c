// SPDX-FileCopyrightText: 2026 Moonshine AI (original C++), Adafruit port
// SPDX-License-Identifier: MIT
//
// Native module `klatt_kernel`: the fixed-point Klatt per-sample loop from klatt_viper.py in C.
// Same interface and arithmetic: render_frame(st, tab, out, n), with st an array('i') laid out
// as in klatt_viper.py, tab the int16 pulse/soft-clip table and out an array('h').
// Built with -fwrapv so signed int32 arithmetic wraps like viper ints; the RNG is uint32.

#include "py/dynruntime.h"

// Layout of the int32 state/coefficient array, as in klatt_viper.py.
enum {
    PHASE, PREV_G, JIT, SHIM, RNG,
    R1Y1, R1Y2, R2Y1, R2Y2, R3Y1, R3Y2, R4Y1, R4Y2, R5Y1, R5Y2,
    NPY1, NPY2, NZX1, NZX2, FX1, FX2, FY1, FY2, OFF,
    R1A, R1B, R1C, R2A, R2B, R2C, R3A, R3B, R3C, R4A, R4B, R4C, R5A, R5B, R5C,
    NPA, NPB, NPC, NZB, NZC, NZG, NASAL_ON,
    FB0, FA1, FA2, FRIC_ON,
    INC0, DINC, AV0, DAV, AV_FROM, AH0, DAH, AF0, DAF, AF_FROM, NAS0, DNAS, NAS_FROM,
    JIT_K, SHIM_K, OUT_G,
    R1AD, R1BD, R1CD, R2AD, R2BD, R2CD, R3AD, R3BD, R3CD,
    PREEMPH, PE_Y1,
    NSLOTS
};

#define TANH_BASE 4097
#define TAB_LEN (TANH_BASE + 257)

static inline uint32_t xorshift(uint32_t r) {
    r ^= r << 13;
    r ^= r >> 17;
    r ^= r << 5;
    return r;
}

// Noise in Q12: r / 2^31 - 1, truncated.
static inline int32_t noise_q12(uint32_t r) {
    return (int32_t)(r >> 19) - 4096;
}

static void c_render_frame(int32_t *st, const int16_t *tab, int16_t *out, int32_t n) {
    int32_t phase = st[PHASE], prev_g = st[PREV_G], jit = st[JIT], shim = st[SHIM];
    uint32_t r = (uint32_t)st[RNG];
    int32_t r1y1 = st[R1Y1], r1y2 = st[R1Y2], r2y1 = st[R2Y1], r2y2 = st[R2Y2];
    int32_t r3y1 = st[R3Y1], r3y2 = st[R3Y2], r4y1 = st[R4Y1], r4y2 = st[R4Y2];
    int32_t r5y1 = st[R5Y1], r5y2 = st[R5Y2];
    int32_t npy1 = st[NPY1], npy2 = st[NPY2], nzx1 = st[NZX1], nzx2 = st[NZX2];
    int32_t fx1 = st[FX1], fx2 = st[FX2], fy1 = st[FY1], fy2 = st[FY2];
    const int32_t off = st[OFF];
    // R1-R3 coefficients are Q22 and step every sample; R4, R5 are Q14 and constant.
    int32_t r1a = st[R1A], r1b = st[R1B], r1c = st[R1C];
    int32_t r2a = st[R2A], r2b = st[R2B], r2c = st[R2C];
    int32_t r3a = st[R3A], r3b = st[R3B], r3c = st[R3C];
    const int32_t r1ad = st[R1AD], r1bd = st[R1BD], r1cd = st[R1CD];
    const int32_t r2ad = st[R2AD], r2bd = st[R2BD], r2cd = st[R2CD];
    const int32_t r3ad = st[R3AD], r3bd = st[R3BD], r3cd = st[R3CD];
    const int32_t r4a = st[R4A], r4b = st[R4B], r4c = st[R4C];
    const int32_t r5a = st[R5A], r5b = st[R5B], r5c = st[R5C];
    const int32_t npa = st[NPA], npb = st[NPB], npc = st[NPC];
    const int32_t nzb = st[NZB], nzc = st[NZC], nzg = st[NZG], nasal_on = st[NASAL_ON];
    const int32_t fb0 = st[FB0], fa1 = st[FA1], fa2 = st[FA2], fric_on = st[FRIC_ON];
    const int32_t inc0 = st[INC0], dinc = st[DINC];
    const int32_t av0 = st[AV0], dav = st[DAV], av_from = st[AV_FROM];
    const int32_t ah0 = st[AH0], dah = st[DAH];
    const int32_t af0 = st[AF0], daf = st[DAF], af_from = st[AF_FROM];
    const int32_t nas0 = st[NAS0], dnas = st[DNAS], nas_from = st[NAS_FROM];
    const int32_t jit_k = st[JIT_K], shim_k = st[SHIM_K], out_g = st[OUT_G];
    const int32_t preemph = st[PREEMPH];
    int32_t pe_y1 = st[PE_Y1];

    for (int32_t s = 0; s < n; s++) {
        // Glottal source: Rosenberg pulse from the table, differentiated.
        int32_t voiced = 0;
        if (s >= av_from) {
            int32_t inc = inc0 + ((dinc * s) >> 8);
            phase += inc + (((inc >> 4) * jit) >> 12);
            if (phase >= 268435456) {
                phase -= 268435456;
                if (jit_k != 0) {
                    r = xorshift(r);
                    jit = (jit_k * noise_q12(r)) >> 12;
                }
                if (shim_k != 0) {
                    r = xorshift(r);
                    shim = 4096 + ((shim_k * noise_q12(r)) >> 12);
                }
            }
            int32_t i = phase >> 16;
            int32_t g0 = (uint16_t)tab[i];
            int32_t g = g0 + ((((int32_t)(uint16_t)tab[i + 1] - g0) * ((phase >> 6) & 1023)) >> 10);
            int32_t exc = g - prev_g;
            prev_g = g;
            voiced = (((exc * (av0 + ((dav * s) >> 8))) >> 12) * shim) >> 12;
        } else {
            prev_g = 0;
        }

        // Aspiration: one noise draw every sample, as in the C++.
        r = xorshift(r);
        int32_t casc = voiced + ((noise_q12(r) * (ah0 + ((dah * s) >> 8))) >> 15);

        // Nasal branch: antiresonator (Q12 numerator, Q10 gain) then pole, blended by nasal.
        if (s >= nas_from && nasal_on != 0) {
            int32_t nz = ((((casc << 14) - nzb * nzx1 - nzc * nzx2 + 8192) >> 14) * nzg) >> 10;
            nzx2 = nzx1;
            nzx1 = casc;
            int32_t nq = (npa * nz + npb * npy1 + npc * npy2 + 8192) >> 14;
            npy2 = npy1;
            npy1 = nq;
            casc = casc + (((nas0 + ((dnas * s) >> 8)) * (nq - casc)) >> 15);
        }

        // Cascade R1-R5.
        int32_t y = ((r1a >> 8) * casc + (r1b >> 8) * r1y1 + (r1c >> 8) * r1y2 + 8192) >> 14;
        r1y2 = r1y1;
        r1y1 = y;
        r1a += r1ad;
        r1b += r1bd;
        r1c += r1cd;
        y = ((r2a >> 8) * y + (r2b >> 8) * r2y1 + (r2c >> 8) * r2y2 + 8192) >> 14;
        r2y2 = r2y1;
        r2y1 = y;
        r2a += r2ad;
        r2b += r2bd;
        r2c += r2cd;
        y = ((r3a >> 8) * y + (r3b >> 8) * r3y1 + (r3c >> 8) * r3y2 + 8192) >> 14;
        r3y2 = r3y1;
        r3y1 = y;
        r3a += r3ad;
        r3b += r3bd;
        r3c += r3cd;
        y = (r4a * y + r4b * r4y1 + r4c * r4y2 + 8192) >> 14;
        r4y2 = r4y1;
        r4y1 = y;
        y = (r5a * y + r5b * r5y1 + r5c * r5y2 + 8192) >> 14;
        r5y2 = r5y1;
        r5y1 = y;

        // Frication: band-passed noise, one draw per sample while af > 0.
        if (s >= af_from) {
            r = xorshift(r);
            if (fric_on != 0) {
                int32_t fx = noise_q12(r);
                int32_t fy = (fb0 * (fx - fx2) - fa1 * fy1 - fa2 * fy2 + 8192) >> 14;
                fx2 = fx1;
                fx1 = fx;
                fy2 = fy1;
                fy1 = fy;
                y += (fy * (af0 + ((daf * s) >> 8))) >> 15;
            }
        }

        // Pre-emphasis, then the stream stage: output gain to int16, soft clip above the 0.8 knee.
        if (preemph != 0) {
            int32_t pe = y - ((preemph * pe_y1) >> 14);
            pe_y1 = y;
            y = pe;
        }
        int32_t v = (y * out_g) >> 12;
        int32_t a = v < 0 ? -v : v;
        if (a > 26214) {
            int32_t e = a - 26214;
            int32_t k = e >> 7;
            if (k >= 256) {
                a = 32767;
            } else {
                int32_t t0 = (uint16_t)tab[TANH_BASE + k];
                a = 26214 + t0 + ((((int32_t)(uint16_t)tab[TANH_BASE + k + 1] - t0) * (e & 127)) >> 7);
            }
            v = v < 0 ? -a : a;
        }
        out[off + s] = (int16_t)v;
    }

    st[PHASE] = phase;
    st[PREV_G] = prev_g;
    st[JIT] = jit;
    st[SHIM] = shim;
    st[RNG] = (int32_t)r;
    st[R1Y1] = r1y1;
    st[R1Y2] = r1y2;
    st[R2Y1] = r2y1;
    st[R2Y2] = r2y2;
    st[R3Y1] = r3y1;
    st[R3Y2] = r3y2;
    st[R4Y1] = r4y1;
    st[R4Y2] = r4y2;
    st[R5Y1] = r5y1;
    st[R5Y2] = r5y2;
    st[NPY1] = npy1;
    st[NPY2] = npy2;
    st[NZX1] = nzx1;
    st[NZX2] = nzx2;
    st[FX1] = fx1;
    st[FX2] = fx2;
    st[FY1] = fy1;
    st[FY2] = fy2;
    st[PE_Y1] = pe_y1;
}

static mp_obj_t mod_render_frame(size_t n_args, const mp_obj_t *args) {
    mp_buffer_info_t st, tab, out;
    mp_get_buffer_raise(args[0], &st, MP_BUFFER_RW);
    mp_get_buffer_raise(args[1], &tab, MP_BUFFER_READ);
    mp_get_buffer_raise(args[2], &out, MP_BUFFER_WRITE);
    mp_int_t n = mp_obj_get_int(args[3]);
    if (st.len < NSLOTS * 4 || tab.len < TAB_LEN * 2) {
        mp_raise_ValueError(MP_ERROR_TEXT("buffer too small"));
    }
    int32_t *s = st.buf;
    if (n < 0 || s[OFF] < 0 || (size_t)(s[OFF] + n) * 2 > out.len) {
        mp_raise_ValueError(MP_ERROR_TEXT("out too small"));
    }
    c_render_frame(s, tab.buf, out.buf, n);
    return MP_OBJ_NEW_SMALL_INT(n);
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(mod_render_frame_obj, 4, 4, mod_render_frame);

mp_obj_t mpy_init(mp_obj_fun_bc_t *self, size_t n_args, size_t n_kw, mp_obj_t *args) {
    MP_DYNRUNTIME_INIT_ENTRY
    mp_store_global(MP_QSTR_render_frame, MP_OBJ_FROM_PTR(&mod_render_frame_obj));
    MP_DYNRUNTIME_INIT_EXIT
}
