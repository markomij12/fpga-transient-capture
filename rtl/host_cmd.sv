// Host-to-FPGA CT command parser. Magic "CT". XOR8 over header+payload, no trailer.
module host_cmd (
    input  logic        clk,
    input  logic        rst,
    input  logic        rx_valid,     // 1-cycle strobe
    input  logic [7:0]  rx_data,
    output logic        arm_pulse,    // 1-cycle
    output logic [11:0] threshold,    // holds last written
    output logic        cmd_error     // 1-cycle
);

    localparam logic [7:0] MAGIC0         = 8'h43;
    localparam logic [7:0] MAGIC1         = 8'h54;
    localparam logic [7:0] VER            = 8'h01;
    localparam logic [7:0] CMD_ARM        = 8'h01;
    localparam logic [7:0] CMD_SET_THRESH = 8'h02;

    typedef enum logic [2:0] {
        ST_IDLE = 3'd0,
        ST_M0   = 3'd1,
        ST_VER  = 3'd2,
        ST_CMD  = 3'd3,
        ST_LEN  = 3'd4,
        ST_PAY  = 3'd5,
        ST_XOR  = 3'd6
    } state_t;

    state_t      state;
    logic [7:0]  acc;
    logic [7:0]  cmd_r;
    logic [1:0]  len_r;
    logic [1:0]  pay_cnt;
    logic [15:0] payload;

    always_ff @(posedge clk) begin
        if (rst) begin
            state     <= ST_IDLE;
            acc       <= 8'h00;
            cmd_r     <= 8'h00;
            len_r     <= 2'd0;
            pay_cnt   <= 2'd0;
            payload   <= 16'h0000;
            threshold <= 12'h800;
            arm_pulse <= 1'b0;
            cmd_error <= 1'b0;
        end else begin
            arm_pulse <= 1'b0;
            cmd_error <= 1'b0;

            case (state)
                ST_IDLE: begin
                    if (rx_valid) begin
                        if (rx_data == MAGIC0) begin
                            acc   <= MAGIC0;
                            state <= ST_M0;
                        end else begin
                            cmd_error <= 1'b1;
                        end
                    end
                end
                ST_M0: begin
                    if (rx_valid) begin
                        if (rx_data == MAGIC1) begin
                            acc   <= acc ^ rx_data;
                            state <= ST_VER;
                        end else begin
                            cmd_error <= 1'b1;
                            state     <= ST_IDLE;
                        end
                    end
                end
                ST_VER: begin
                    if (rx_valid) begin
                        if (rx_data == VER) begin
                            acc   <= acc ^ rx_data;
                            state <= ST_CMD;
                        end else begin
                            cmd_error <= 1'b1;
                            state     <= ST_IDLE;
                        end
                    end
                end
                ST_CMD: begin
                    if (rx_valid) begin
                        cmd_r <= rx_data;
                        acc   <= acc ^ rx_data;
                        state <= ST_LEN;
                    end
                end
                ST_LEN: begin
                    if (rx_valid) begin
                        if (rx_data > 8'd2) begin
                            cmd_error <= 1'b1;
                            state     <= ST_IDLE;
                        end else begin
                            len_r   <= rx_data[1:0];
                            acc     <= acc ^ rx_data;
                            pay_cnt <= 2'd0;
                            payload <= 16'h0000;
                            if (rx_data == 8'd0)
                                state <= ST_XOR;
                            else
                                state <= ST_PAY;
                        end
                    end
                end
                ST_PAY: begin
                    if (rx_valid) begin
                        acc <= acc ^ rx_data;
                        if (pay_cnt == 2'd0)
                            payload <= {8'h00, rx_data};
                        else
                            payload <= {rx_data, payload[7:0]};
                        if ((pay_cnt + 2'd1) == len_r)
                            state <= ST_XOR;
                        else
                            pay_cnt <= pay_cnt + 2'd1;
                    end
                end
                ST_XOR: begin
                    if (rx_valid) begin
                        state <= ST_IDLE;
                        if (rx_data != acc) begin
                            cmd_error <= 1'b1;
                        end else if ((cmd_r == CMD_ARM) && (len_r == 2'd0)) begin
                            arm_pulse <= 1'b1;
                        end else if ((cmd_r == CMD_SET_THRESH) && (len_r == 2'd2)) begin
                            threshold <= payload[11:0];
                        end else begin
                            cmd_error <= 1'b1;
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
