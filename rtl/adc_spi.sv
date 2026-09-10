// AD7476A / Pmod AD1 SPI master, Mode 3 (CPOL=1, CPHA=1).
// 16 SCLK cycles: 4 leading zeros + 12-bit MSB first (DB11..DB0).
// CLKS_PER_SCLK = sysclk / sclk. 100 MHz / 20 MHz = 5.
// SAMPLE_PERIOD_CLKS = sysclk / sample_rate. 100 MHz / 1 MSPS = 100.
// SAMPLE_PERIOD_CLKS must be >= 16*CLKS_PER_SCLK + 5.
module adc_spi #(
    parameter int CLKS_PER_SCLK      = 5,
    parameter int SAMPLE_PERIOD_CLKS = 100
) (
    input  logic        clk,
    input  logic        rst,
    input  logic        enable,
    output logic        cs_n,
    output logic        sclk,
    input  logic        sdata,
    output logic [11:0] sample,
    output logic        sample_valid
);

    localparam int SclkCntWidth   = $clog2(CLKS_PER_SCLK);
    localparam int PeriodCntWidth = $clog2(SAMPLE_PERIOD_CLKS);
    localparam int LowClks        = CLKS_PER_SCLK / 2;

    typedef enum logic [1:0] {
        ST_IDLE  = 2'd0,
        ST_SETUP = 2'd1,
        ST_CLOCK = 2'd2
    } state_t;

    state_t                    state;
    logic [PeriodCntWidth-1:0] period_cnt;
    logic [SclkCntWidth-1:0]   sclk_cnt;
    logic [3:0]                bit_idx;
    logic [11:0]               shift_r;

    always_ff @(posedge clk) begin
        if (rst) begin
            state        <= ST_IDLE;
            period_cnt   <= '0;
            sclk_cnt     <= '0;
            bit_idx      <= '0;
            shift_r      <= '0;
            cs_n         <= 1'b1;
            sclk         <= 1'b1;
            sample       <= '0;
            sample_valid <= 1'b0;
        end else if (!enable) begin
            state        <= ST_IDLE;
            period_cnt   <= '0;
            sclk_cnt     <= '0;
            bit_idx      <= '0;
            shift_r      <= '0;
            cs_n         <= 1'b1;
            sclk         <= 1'b1;
            sample_valid <= 1'b0;
        end else begin
            sample_valid <= 1'b0;

            if (period_cnt == PeriodCntWidth'(SAMPLE_PERIOD_CLKS - 1)) begin
                period_cnt <= '0;
            end else begin
                period_cnt <= period_cnt + 1'b1;
            end

            case (state)
                ST_IDLE: begin
                    cs_n <= 1'b1;
                    sclk <= 1'b1;
                    if (period_cnt == '0) begin
                        cs_n  <= 1'b0;
                        state <= ST_SETUP;
                    end
                end
                ST_SETUP: begin
                    // t2: CS low, SCLK still high for 1 sysclk, then first fall.
                    cs_n     <= 1'b0;
                    sclk     <= 1'b0;
                    sclk_cnt <= '0;
                    bit_idx  <= '0;
                    shift_r  <= '0;
                    state    <= ST_CLOCK;
                end
                ST_CLOCK: begin
                    cs_n <= 1'b0;
                    if (sclk_cnt == SclkCntWidth'(CLKS_PER_SCLK - 1)) begin
                        if (bit_idx == 4'd15) begin
                            cs_n  <= 1'b1;
                            sclk  <= 1'b1;
                            state <= ST_IDLE;
                        end else begin
                            bit_idx  <= bit_idx + 1'b1;
                            sclk_cnt <= '0;
                            sclk     <= 1'b0;
                        end
                    end else begin
                        sclk_cnt <= sclk_cnt + 1'b1;
                        if (sclk_cnt == SclkCntWidth'(LowClks - 1)) begin
                            sclk <= 1'b1;
                            // Rising edges 4..15 (bit_idx 3..14) are DB11..DB0.
                            // Rising 16 (bit_idx 15) is Hi-Z; do not capture.
                            if (bit_idx >= 4'd3 && bit_idx <= 4'd14) begin
                                shift_r <= {shift_r[10:0], sdata};
                            end
                            if (bit_idx == 4'd14) begin
                                sample       <= {shift_r[10:0], sdata};
                                sample_valid <= 1'b1;
                            end
                        end else if (sclk_cnt < SclkCntWidth'(LowClks - 1)) begin
                            sclk <= 1'b0;
                        end else begin
                            sclk <= 1'b1;
                        end
                    end
                end
                default: begin
                    state <= ST_IDLE;
                end
            endcase
        end
    end

endmodule
