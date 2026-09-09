// UART transmitter, 8N1.
// CLKS_PER_BIT = clock_hz / baud. 100 MHz / 115200 ≈ 868.
module uart_tx #(
    parameter CLKS_PER_BIT = 868
) (
    input  logic       clk,
    input  logic       rst,
    input  logic       tx_start,
    input  logic [7:0] tx_data,
    output logic       tx,
    output logic       tx_busy
);

    localparam int CntWidth = $clog2(CLKS_PER_BIT);

    typedef enum logic [1:0] {
        ST_IDLE  = 2'd0,
        ST_START = 2'd1,
        ST_DATA  = 2'd2,
        ST_STOP  = 2'd3
    } state_t;

    state_t              state;
    logic [CntWidth-1:0] clk_cnt;
    logic [2:0]          bit_idx;
    logic [7:0]          data_r;

    assign tx_busy = (state != ST_IDLE);

    always_ff @(posedge clk) begin
        if (rst) begin
            state   <= ST_IDLE;
            clk_cnt <= '0;
            bit_idx <= '0;
            data_r  <= '0;
            tx      <= 1'b1;
        end else begin
            case (state)
                ST_IDLE: begin
                    tx      <= 1'b1;
                    clk_cnt <= '0;
                    bit_idx <= '0;
                    if (tx_start) begin
                        data_r <= tx_data;
                        state  <= ST_START;
                    end
                end
                ST_START: begin
                    tx <= 1'b0;
                    if (clk_cnt == CntWidth'(CLKS_PER_BIT - 1)) begin
                        clk_cnt <= '0;
                        state   <= ST_DATA;
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end
                ST_DATA: begin
                    tx <= data_r[bit_idx];
                    if (clk_cnt == CntWidth'(CLKS_PER_BIT - 1)) begin
                        clk_cnt <= '0;
                        if (bit_idx == 3'd7) begin
                            bit_idx <= '0;
                            state   <= ST_STOP;
                        end else begin
                            bit_idx <= bit_idx + 1'b1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end
                ST_STOP: begin
                    tx <= 1'b1;
                    if (clk_cnt == CntWidth'(CLKS_PER_BIT - 1)) begin
                        clk_cnt <= '0;
                        state   <= ST_IDLE;
                    end else begin
                        clk_cnt <= clk_cnt + 1'b1;
                    end
                end
                default: begin
                    state <= ST_IDLE;
                end
            endcase
        end
    end

endmodule
